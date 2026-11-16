"""Exercise the isolated service through its HTTP routes and own database."""
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.utils import timezone

from discovery import services
from discovery.models import Event


class ServiceApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('owner', password='a-test-password')
        cls.other = get_user_model().objects.create_user('other', password='another-test-password')
        cls.admin = get_user_model().objects.create_superuser('admin', password='admin-test-password')
        cls.category = services.save_category(actor=cls.admin, data={
            'name': 'House', 'color': '#123456', 'description': 'Music'})
        cls.venue = services.save_venue(actor=cls.admin, review_status='approved', data={
            'name': 'Venue', 'latitude': 48, 'longitude': 2, 'timezone': 'Europe/Paris'})

    def post(self, url, data, token=None):
        headers = {'HTTP_AUTHORIZATION': 'Bearer ' + token} if token else {}
        return self.client.post(url, json.dumps(data), content_type='application/json', **headers)

    def token(self, username='owner', password='a-test-password'):
        response = self.post('/api/auth/token/', {'username': username, 'password': password})
        self.assertEqual(response.status_code, 200)
        return response.json()['token']

    def payload(self):
        start = timezone.now() + timedelta(days=1)
        return {'category_ids': [self.category.pk], 'event': {
            'venue_id': self.venue.pk, 'title': 'A night', 'description': 'Music',
            'starts_at': start.isoformat(), 'ends_at': (start + timedelta(hours=3)).isoformat()}}

    def test_authentication_logout_and_no_cookie(self):
        token = self.token()
        self.assertFalse(self.client.cookies)
        response = self.client.get('/api/auth/identity/', HTTP_AUTHORIZATION='Bearer '+token)
        self.assertEqual(response.json(), {'id': self.owner.pk, 'display_name': 'owner',
                                          'active': True, 'permissions': []})
        self.assertEqual(self.post('/api/auth/logout/', {}, token).status_code, 200)
        self.assertEqual(self.client.get('/api/auth/identity/', HTTP_AUTHORIZATION='Bearer '+token).status_code, 401)

    def test_bad_credentials_missing_expired_and_password_changed_tokens(self):
        self.assertEqual(self.post('/api/auth/token/', {'username': 'owner', 'password': 'bad'}).status_code, 401)
        self.assertEqual(self.client.get('/api/auth/identity/').status_code, 401)
        token = self.token()
        Session.objects.filter(session_key=token).update(expire_date=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.get('/api/auth/identity/', HTTP_AUTHORIZATION='Bearer '+token).status_code, 401)
        token = self.token()
        self.owner.set_password('changed-test-password')
        self.owner.save()
        self.assertEqual(self.client.get('/api/auth/identity/', HTTP_AUTHORIZATION='Bearer '+token).status_code, 401)

    def test_deactivated_account_is_forbidden(self):
        token = self.token()
        get_user_model().objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertEqual(self.client.get('/api/auth/identity/', HTTP_AUTHORIZATION='Bearer '+token).status_code, 403)

    def test_create_browse_edit_and_ownership(self):
        token = self.token()
        created = self.post('/api/events/', self.payload(), token)
        self.assertEqual(created.status_code, 201)
        pk = created.json()['id']
        self.assertEqual(Event.objects.get(pk=pk).creator_id, self.owner.pk)
        self.assertEqual(self.client.get('/api/events/').json()['events'][0]['id'], pk)
        self.assertEqual(self.client.get(f'/api/events/{pk}/').status_code, 200)
        other_token = self.token('other', 'another-test-password')
        payload = self.payload()
        payload['event']['title'] = 'Changed'
        url = f'/api/events/{pk}/edit/'
        self.assertEqual(self.client.put(url, json.dumps(payload), content_type='application/json',
                         HTTP_AUTHORIZATION='Bearer '+other_token).status_code, 403)
        self.assertEqual(self.client.put(url, json.dumps(payload), content_type='application/json',
                         HTTP_AUTHORIZATION='Bearer '+token).status_code, 200)
        self.assertEqual(self.client.get(f'/api/events/{pk}/').json()['title'], 'Changed')

    def test_forged_fields_and_invalid_input_do_not_create_rows(self):
        token = self.token()
        payload = self.payload()
        payload['event']['creator_id'] = self.other.pk
        self.assertEqual(self.post('/api/events/', payload, token).status_code, 400)
        for payload in ([], {}, {'event': []}, {'event': {'starts_at': 'invalid'}}):
            self.assertEqual(self.post('/api/events/', payload, token).status_code, 400)
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(self.post('/api/events/', self.payload()).status_code, 401)

    def test_follow_is_idempotent_and_inboxes_are_scoped(self):
        owner_token = self.token()
        pk = self.post('/api/events/', self.payload(), owner_token).json()['id']
        other_token = self.token('other', 'another-test-password')
        for _ in range(2):
            self.assertEqual(self.post(f'/api/events/{pk}/follow/', {}, other_token).status_code, 200)
        payload = self.payload()
        payload['event']['starts_at'] = (timezone.now()+timedelta(days=2)).isoformat()
        payload['event']['ends_at'] = (timezone.now()+timedelta(days=2,hours=4)).isoformat()
        self.assertEqual(self.client.put(f'/api/events/{pk}/edit/', json.dumps(payload),
            content_type='application/json', HTTP_AUTHORIZATION='Bearer '+owner_token).status_code, 200)
        self.assertEqual(len(self.client.get('/api/notifications/', HTTP_AUTHORIZATION='Bearer '+other_token).json()['notifications']), 1)
        self.assertEqual(self.client.get('/api/notifications/', HTTP_AUTHORIZATION='Bearer '+owner_token).json()['notifications'], [])

    @override_settings(UI_ORIGIN='https://ui.example', VERSION='test-sha')
    def test_health_cors_and_request_logs(self):
        with self.assertLogs('requests', level='INFO') as logs:
            response = self.client.get('/health', HTTP_ORIGIN='https://ui.example')
        self.assertEqual(response.json(), {'status': 'ok', 'db': 'ok', 'version': 'test-sha'})
        self.assertEqual(response['Access-Control-Allow-Origin'], 'https://ui.example')
        self.assertIn('GET /health 200', logs.output[0])
        self.assertNotIn('Access-Control-Allow-Origin', self.client.get('/health', HTTP_ORIGIN='https://wrong.example'))
        preflight = self.client.options('/api/events/', HTTP_ORIGIN='https://ui.example')
        self.assertEqual(preflight.status_code, 204)

    def test_database_failure_is_503_and_no_groups_are_installed(self):
        from django.apps import apps
        self.assertFalse(apps.is_installed('groups'))
        with patch('config.api.HealthProbe.objects.get_or_create', side_effect=OperationalError('offline')):
            self.assertEqual(self.client.get('/health').status_code, 503)

    def test_seed_twice_keeps_existing_operator_edits(self):
        from discovery.models import GenreCategory, GenreTag
        call_command('seed_discovery', verbosity=0)
        category = GenreCategory.objects.get(name='House')
        category.description = 'Operator edit'
        category.save(update_fields=['description'])
        counts = (GenreCategory.objects.count(), GenreTag.objects.count())
        call_command('seed_discovery', verbosity=0)
        category.refresh_from_db()
        self.assertEqual(category.description, 'Operator edit')
        self.assertEqual(counts, (GenreCategory.objects.count(), GenreTag.objects.count()))
