"""Account privacy, forged fields, real form validation and rate-limit boundaries."""
import json
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from django.http import JsonResponse
from zoneinfo import ZoneInfo
from django.utils import timezone
from accounts.models import AuthWindow
from discovery import services
from discovery.models import Event, EventChange
from .authentication import issue_token
from .throttle import limited


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser('owner', password='local-test-password')
        cls.other = get_user_model().objects.create_user('other', password='other-test-password')
        cls.category = services.save_category(actor=cls.owner, data={'name': 'House', 'color': '#aa3311', 'description': 'Music'})
        cls.venue = services.save_venue(actor=cls.owner, review_status='approved', data={
            'name': 'Venue', 'latitude': '40.4', 'longitude': '-3.7', 'timezone': 'Europe/Madrid'})

    def call(self, path, data=None, *, actor='owner', method='post'):
        headers = {'HTTP_AUTHORIZATION': 'Bearer '+issue_token(actor, 'local-test-password' if actor == 'owner' else 'other-test-password')} if actor else {}
        if method == 'get':
            return self.client.get(path, **headers)
        return getattr(self.client, method)(path, json.dumps(data), content_type='application/json', **headers)

    def payload(self):
        day = (timezone.now()+timedelta(days=3)).strftime('%Y-%m-%d')
        return {'venue': self.venue.pk, 'title': 'Local night', 'description': 'Original',
            'starts_at': day+'T20:00', 'ends_at': day+'T23:00', 'ticket_url': '',
            'categories': [self.category.pk], 'tags': [], 'performers': []}

    def test_registration_password_rules_and_forged_privilege(self):
        data = {'username': 'newperson', 'password1': 'password', 'password2': 'password'}
        self.assertEqual(self.call('/api/auth/register/', data, actor=None).status_code, 400)
        data.update(password1='Distant-comet-471!', password2='Distant-comet-471!')
        self.assertEqual(self.call('/api/auth/register/', {**data, 'is_superuser': True}, actor=None).status_code, 400)
        self.assertEqual(self.call('/api/auth/register/', data, actor=None).status_code, 201)
        self.assertFalse(get_user_model().objects.get(username='newperson').is_staff)
        self.assertEqual(self.call('/api/auth/register/', data, actor=None).status_code, 400)

    def test_profile_is_self_only_and_social_domains_checked(self):
        self.owner.email = 'private@example.com'; self.owner.save()
        mine = self.call('/api/account/', method='get').json()
        theirs = self.call('/api/account/', actor='other', method='get').json()
        self.assertEqual(mine['email'], 'private@example.com')
        self.assertEqual(theirs['email'], '')
        data = {key: mine[key] for key in ('display_name', 'bio', 'email', 'instagram_url', 'spotify_url', 'apple_music_url', 'soundcloud_url')}
        self.assertEqual(self.call('/api/account/', {**data, 'id': self.other.pk}, method='put').status_code, 400)
        data['spotify_url'] = 'https://example.com/fake'
        self.assertEqual(self.call('/api/account/', data, method='put').status_code, 400)
        data['spotify_url'] = 'https://open.spotify.com/user/example'
        self.assertEqual(self.call('/api/account/', data, method='put').status_code, 200)
        self.assertEqual(self.call('/api/account/', actor=None, method='get').status_code, 401)

    def test_event_form_timezone_ownership_and_cancellation(self):
        payload = self.payload()
        response = self.call('/api/event-form/', payload)
        self.assertEqual(response.status_code, 201, response.content)
        pk = response.json()['id']; event = Event.objects.get(pk=pk)
        self.assertEqual(event.starts_at.astimezone(ZoneInfo('Europe/Madrid')).hour, 20)
        self.assertEqual(self.call(f'/api/event-form/{pk}/', method='get').json()['initial']['starts_at'], payload['starts_at'])
        self.assertEqual(self.call(f'/api/event-form/{pk}/', payload, method='put', actor='other').status_code, 403)
        self.assertEqual(self.call('/api/my-events/', method='get').json()['owned'][0]['id'], pk)
        payload['title'] = 'Updated night'
        self.assertEqual(self.call(f'/api/event-form/{pk}/', payload, method='put').status_code, 200)
        self.assertEqual(self.call(f'/api/events/{pk}/cancel/', {}).status_code, 200)
        event.refresh_from_db(); self.assertIsNotNone(event.cancelled_at)

    def test_form_rejects_dst_gap_and_unknown_fields(self):
        payload = self.payload(); payload.update(starts_at='2027-03-28T02:30', ends_at='2027-03-28T05:00')
        self.assertEqual(self.call('/api/event-form/', payload).status_code, 400)
        self.assertEqual(self.call('/api/event-form/', {**self.payload(), 'creator_id': self.other.pk}).status_code, 400)
        self.assertEqual(self.call('/api/event-form/', {**self.payload(), 'starts_at': 123}).status_code, 400)
        self.assertEqual(Event.objects.count(), 0)

    def test_proposed_venue_remains_pending_and_report_is_recipient_scoped(self):
        venue = self.call('/api/venues/propose/', {'name': 'Pending', 'address': '', 'latitude': '40', 'longitude': '-3', 'timezone': 'Europe/Madrid'}, actor='other')
        self.assertEqual(venue.status_code, 201)
        self.assertEqual(venue.json()['review_status'], 'pending')
        pk = self.call('/api/event-form/', self.payload()).json()['id']
        self.assertEqual(self.call(f'/api/events/{pk}/report/', {'reason': 'other', 'explanation': 'Needs review'}, actor='other').status_code, 201)
        from notifications.models import Notification
        change = EventChange.objects.create(event_id=pk, actor=self.owner, kind='event_edit', changes={})
        n = Notification.objects.create(recipient=self.owner, event_change=change, summary='Private')
        self.assertEqual(self.call(f'/api/notifications/{n.pk}/read/', {}, actor='other').status_code, 404)
        self.assertEqual(self.call(f'/api/notifications/{n.pk}/read/', {}).status_code, 200)

    def test_shared_throttle_expires_and_stores_no_raw_identifiers(self):
        request = RequestFactory().post('/', REMOTE_ADDR='192.0.2.45')
        with patch('config.throttle.time', return_value=6000):
            for _ in range(20): self.assertIsNone(limited(request, 'login', 'private-name'))
            self.assertEqual(limited(request, 'login', 'private-name').status_code, 429)
        self.assertNotIn('private-name', str(list(AuthWindow.objects.values())))
        with patch('config.throttle.time', return_value=6060):
            self.assertIsNone(limited(request, 'login', 'private-name'))
        with patch('config.account_api.limited', return_value=JsonResponse({'error': 'Limited'}, status=429)):
            self.assertEqual(self.call('/api/auth/register/', {}, actor=None).status_code, 429)

    def test_forwarded_ip_is_opt_in_and_only_trusted_rightmost_hop_counts(self):
        factory = RequestFactory()
        with patch('config.throttle.time', return_value=6000):
            with override_settings(TRUST_CONTAINER_APPS_INGRESS=False):
                for _ in range(10): self.assertIsNone(limited(factory.post('/', HTTP_X_FORWARDED_FOR='198.51.100.1'), 'register'))
                self.assertEqual(limited(factory.post('/', HTTP_X_FORWARDED_FOR='198.51.100.2'), 'register').status_code, 429)
            AuthWindow.objects.all().delete()
            with override_settings(TRUST_CONTAINER_APPS_INGRESS=True):
                for _ in range(10): self.assertIsNone(limited(factory.post('/', HTTP_X_FORWARDED_FOR='spoofed, 198.51.100.1'), 'register'))
                self.assertEqual(limited(factory.post('/', HTTP_X_FORWARDED_FOR='different, 198.51.100.1'), 'register').status_code, 429)
                self.assertIsNone(limited(factory.post('/', HTTP_X_FORWARDED_FOR='198.51.100.2'), 'register'))
                self.assertIsNone(limited(factory.post('/', HTTP_X_FORWARDED_FOR='invalid'), 'register'))

    def test_username_limit_normalizes_unicode_and_endpoint_returns_429(self):
        request = RequestFactory().post('/')
        with patch('config.throttle.time', return_value=6000):
            for _ in range(20): self.assertIsNone(limited(request, 'login', 'Ａlice'))
            self.assertEqual(limited(request, 'login', 'Alice').status_code, 429)
        with patch('config.api.limited', return_value=JsonResponse({'error': 'Limited'}, status=429)):
            self.assertEqual(self.call('/api/auth/token/', {'username': 'owner', 'password': 'bad'}, actor=None).status_code, 429)
