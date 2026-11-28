"""The operator command that loads the fictional Assignment 1 demo content."""
import json
import os
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from discovery.models import Event, EventCard, EventFollow, Venue
from discovery.services import public_events

PASSWORD = 'Distant-comet-demo-471'


class DemoContentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_discovery', stdout=StringIO())

    def load(self, *arguments, password=PASSWORD):
        output = StringIO()
        with patch.dict(os.environ, {'DEMO_ACCOUNT_PASSWORD': password}):
            call_command('seed_demo_content', *arguments, stdout=output)
        return output.getvalue()

    def test_loads_upcoming_public_events_once_without_printing_the_password(self):
        output = self.load()
        result = json.loads(output.strip().splitlines()[-1])
        self.assertEqual((result['events'], result['events_created'], len(result['accounts'])), (25, 25, 12))
        self.assertNotIn(PASSWORD, output)
        now = timezone.now()
        events = Event.objects.all()
        self.assertTrue(all(now < e.starts_at < now + timedelta(days=66) for e in events))
        self.assertEqual(public_events().count(), 25)
        self.assertTrue(all(e.demo_poster and 'Fictional demo listing.' in e.description for e in events))
        rick = get_user_model().objects.get(username='rick_sanchez')
        self.assertTrue(rick.check_password(PASSWORD))
        self.assertFalse(rick.is_staff or rick.is_superuser)
        self.assertEqual(EventCard.objects.filter(user=rick).count(), 18)
        self.assertTrue(Venue.objects.filter(review_status='pending').exists())
        counts = (Event.objects.count(), Venue.objects.count(), EventCard.objects.count(), EventFollow.objects.count())
        again = json.loads(self.load().strip().splitlines()[-1])
        self.assertEqual((again['events_created'], again['events_moved']), (0, 0))
        self.assertEqual(counts, (Event.objects.count(), Venue.objects.count(), EventCard.objects.count(),
                                  EventFollow.objects.count()))

    def test_dates_move_forward_only_when_asked(self):
        self.load()
        event = Event.objects.get(title='Blue Hour Circuit')
        planned = event.starts_at
        Event.objects.filter(pk=event.pk).update(starts_at=planned - timedelta(days=90),
                                                 ends_at=event.ends_at - timedelta(days=90))
        self.load()
        self.assertLess(Event.objects.get(pk=event.pk).starts_at, timezone.now())
        moved = json.loads(self.load('--refresh-dates').strip().splitlines()[-1])
        self.assertEqual(moved['events_moved'], 1)
        self.assertEqual(Event.objects.get(pk=event.pk).starts_at, planned)

    def test_refuses_weak_wrong_or_foreign_accounts_and_changes_nothing(self):
        with self.assertRaisesMessage(CommandError, 'at least 12'):
            self.load(password='short')
        with self.assertRaisesMessage(CommandError, 'was rejected'):
            self.load(password='123456789012')
        get_user_model().objects.create_user('rick_sanchez', password='someone-elses-account')
        with self.assertRaisesMessage(CommandError, 'Refusing to adopt'):
            self.load()
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(Event.objects.exists())
        get_user_model().objects.all().delete()
        self.load()
        with self.assertRaisesMessage(CommandError, 'does not match'):
            self.load(password='Another-comet-demo-912')
