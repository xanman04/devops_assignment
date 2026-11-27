"""Organiser listening links and the private event-card collection."""
import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from discovery import collection, services
from discovery.models import EventCard, EventListeningReference
from .authentication import issue_token

PASSWORD = 'local-test-password'


class Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model().objects
        cls.admin = users.create_superuser('curator', password=PASSWORD)
        cls.organiser = users.create_user('organiser', password=PASSWORD)
        cls.other = users.create_user('other', password=PASSWORD)
        cls.category = services.save_category(actor=cls.admin, data={
            'name': 'House', 'color': '#aa3311', 'description': 'Music'})
        cls.venue = services.save_venue(actor=cls.admin, review_status='approved', data={
            'name': 'Venue', 'latitude': '40.4', 'longitude': '-3.7', 'timezone': 'Europe/Madrid'})

    @classmethod
    def event(cls, title, days=3):
        start = timezone.now() + timedelta(days=days)
        return services.save_event(actor=cls.organiser, category_ids=[cls.category.pk], data={
            'venue': cls.venue, 'title': title, 'description': 'Description',
            'starts_at': start, 'ends_at': start + timedelta(hours=3)})

    def call(self, path, data=None, *, actor='organiser', method='get'):
        headers = {'HTTP_AUTHORIZATION': 'Bearer ' + issue_token(actor, PASSWORD)} if actor else {}
        if method == 'get':
            return self.client.get(path, **headers)
        return getattr(self.client, method)(path, json.dumps(data), content_type='application/json', **headers)


class ListeningLinkTests(Fixture):
    def setUp(self):
        self.night = self.event('Own night')
        self.base = f'/api/events/{self.night.pk}/references/'
        self.link = {'title': 'Warm-up', 'artist_credit': 'Selector', 'kind': 'set',
                     'url': 'https://soundcloud.com/example/warm-up', 'display_order': 1}

    def test_organiser_adds_edits_and_removes_a_public_link(self):
        created = self.call(self.base, self.link, method='post')
        self.assertEqual(created.status_code, 201)
        reference = created.json()
        self.assertEqual({**self.link, 'id': reference['id']}, reference)
        listed = self.call(self.base).json()
        self.assertEqual(listed, {'event': {'id': self.night.pk, 'title': 'Own night'}, 'references': [reference]})
        changed = self.call(f'{self.base}{reference["id"]}/', {**self.link, 'title': 'Closing'}, method='put')
        self.assertEqual(changed.json()['title'], 'Closing')
        public = self.client.get(f'/api/events/{self.night.pk}/content/').json()
        self.assertEqual([r['title'] for r in public['references']], ['Closing'])
        removed = self.call(f'{self.base}{reference["id"]}/delete/', {}, method='post')
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.call(self.base).json()['references'], [])

    def test_only_the_creator_or_an_authorised_editor_may_use_them(self):
        reference = self.call(self.base, self.link, method='post').json()
        item = f'{self.base}{reference["id"]}/'
        attempts = ((self.base, None, 'get'), (self.base, self.link, 'post'),
                    (item, {**self.link, 'title': 'Taken'}, 'put'), (item + 'delete/', {}, 'post'))
        for path, data, method in attempts:
            self.assertEqual(self.call(path, data, actor=None, method=method).status_code, 401, path)
            self.assertEqual(self.call(path, data, actor='other', method=method).status_code, 403, path)
        self.assertEqual(EventListeningReference.objects.get().title, 'Warm-up')
        self.assertEqual(self.call(self.base, actor='curator').status_code, 200)

    def test_hidden_events_look_missing_to_everyone_but_their_editors(self):
        self.night.moderation_hidden = True
        self.night.save(update_fields=['moderation_hidden'])
        self.assertEqual(self.call(self.base, actor='other').status_code, 404)
        self.assertEqual(self.call(self.base).status_code, 200)

    def test_a_reference_cannot_be_reached_through_another_event(self):
        reference = self.call(self.base, self.link, method='post').json()
        second = self.event('Second night')
        foreign = f'/api/events/{second.pk}/references/{reference["id"]}/'
        self.assertEqual(self.call(foreign, self.link, method='put').status_code, 404)
        self.assertEqual(self.call(foreign + 'delete/', {}, method='post').status_code, 404)
        self.assertTrue(EventListeningReference.objects.filter(pk=reference['id'], event=self.night).exists())

    def test_invalid_links_and_forged_fields_are_rejected(self):
        for change in ({'url': 'javascript:alert(1)'}, {'url': 'not a link'}, {'kind': 'video'}, {'title': ''},
                       {'title': 'x' * 201}, {'artist_credit': 5}, {'display_order': -1}, {'display_order': True},
                       {'display_order': '1'}, {'display_order': 2147483648}, {'event': self.night.pk}):
            response = self.call(self.base, {**self.link, **change}, method='post')
            self.assertEqual(response.status_code, 400, change)
        missing = {key: value for key, value in self.link.items() if key != 'kind'}
        self.assertEqual(self.call(self.base, missing, method='post').status_code, 400)
        self.assertFalse(EventListeningReference.objects.exists())


class CollectionTests(Fixture):
    def attend(self, user, number):
        events = [self.event(f'Night {user.username} {i}', days=-10 - i) for i in range(number)]
        for event in events:
            EventCard.objects.create(user=user, event=event)
        return events

    def test_collection_is_private_and_starts_empty(self):
        self.assertEqual(self.call('/api/account/collection/', actor=None).status_code, 401)
        self.attend(self.other, 3)
        mine = self.call('/api/account/collection/').json()
        self.assertEqual(mine, {'name': 'Collection', 'total_slots': 20, 'followed': 0,
                                'cards': [], 'achievements': []})

    def test_cards_prove_achievements_and_hidden_events_stop_counting(self):
        events = self.attend(self.organiser, 3)
        services.follow_event(actor=self.organiser, event_id=events[0].pk)
        data = self.call('/api/account/collection/').json()
        self.assertEqual(data['followed'], 1)
        self.assertEqual([c['event_id'] for c in data['cards']], [e.pk for e in events])
        self.assertEqual(data['cards'][0]['genre'], 'House')
        self.assertEqual({(a['title'], a['tier']) for a in data['achievements']},
                         {('Scene Regular', 'Bronze'), ('House Regular', 'Bronze')})
        self.assertEqual(sorted(data['achievements'][0]['event_ids']), sorted(e.pk for e in events))
        events[0].moderation_hidden = True
        events[0].save(update_fields=['moderation_hidden'])
        data = self.call('/api/account/collection/').json()
        self.assertEqual((len(data['cards']), data['achievements'], data['followed']), (2, [], 0))

    def test_tiers_follow_thresholds_and_highest_comes_first(self):
        cards = [{'event_id': i, 'genre': 'Techno' if i < 5 else 'Ambient'} for i in range(8)]
        earned = collection.achievements(cards)
        self.assertEqual([(a['title'], a['tier']) for a in earned],
                         [('Scene Regular', 'Silver'), ('Techno Head', 'Silver'), ('Ambient Fan', 'Bronze')])
        self.assertEqual(collection.achievements(cards[:2]), [])
