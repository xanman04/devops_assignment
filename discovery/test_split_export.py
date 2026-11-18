"""The source export retains IDs while removing cross-owner relations."""
import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from groups import services as groups
from . import services


class SplitExportTests(TestCase):
    def test_export_ownership_stable_ids_and_private_destination(self):
        user = get_user_model().objects.create_superuser('export-owner', password='synthetic-export-test')
        category = services.save_category(actor=user, data={'name': 'House', 'color': '#123456', 'description': 'Test'})
        venue = services.save_venue(actor=user, review_status='approved', data={
            'name': 'Venue', 'latitude': 48, 'longitude': 2, 'timezone': 'Europe/Paris'})
        start = timezone.now()+timedelta(days=2)
        event = services.save_event(actor=user, category_ids=[category.pk], data={
            'venue': venue, 'title': 'Event', 'description': 'Test', 'starts_at': start, 'ends_at': start+timedelta(hours=4)})
        group = groups.save_group(actor=user, data={'event': event, 'name': 'Group', 'description': 'Test',
            'capacity': 4, 'joining_mode': 'public'})
        with TemporaryDirectory() as directory, override_settings(DATA_DIR=Path(directory)):
            target = Path(directory)/'split.json'
            call_command('export_split_data', str(target))
            data = json.loads(target.read_text())
            user_row = next(row for row in data['discovery'] if row['model'] == 'accounts.user')
            self.assertEqual(user_row['pk'], user.pk)
            self.assertEqual(user_row['fields']['password'], user.password)
            person = next(row for row in data['groups'] if row['model'] == 'groups.person')
            self.assertEqual(person, {'model': 'groups.person', 'pk': user.pk, 'fields': {'display_name': user.public_name}})
            group_row = next(row for row in data['groups'] if row['model'] == 'groups.attendancegroup')
            self.assertEqual((group_row['pk'], group_row['fields']['event_id'], group_row['fields']['owner']),
                             (group.pk, event.pk, user.pk))
            self.assertNotIn('event', group_row['fields'])
            self.assertNotIn('accounts.user', {row['model'] for row in data['groups']})
            self.assertNotIn('django_session', target.read_text())
            with self.assertRaises(CommandError):
                call_command('export_split_data', str(target))
            with self.assertRaises(CommandError):
                call_command('export_split_data', str(Path(directory).parent/'public-export.json'))
