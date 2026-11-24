import json
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase


class ModeratorGrantTests(TestCase):
    def grant(self, username):
        output = StringIO()
        with patch.dict('os.environ', {'MODERATOR_USERNAME': username}):
            call_command('grant_moderator', stdout=output)
        return json.loads(output.getvalue())

    def test_only_review_permissions_added_password_and_flags_preserved(self):
        user = get_user_model().objects.create_user('selected', password='local-test-only')
        password_hash = user.password
        self.grant('selected'); self.grant('selected')
        user.refresh_from_db()
        self.assertEqual(user.password, password_hash)
        self.assertFalse(user.is_staff); self.assertFalse(user.is_superuser)
        self.assertEqual(set(user.user_permissions.values_list('codename', flat=True)),
                         {'change_venue', 'change_eventreport', 'hide_reported_event'})
        self.assertFalse(user.has_perm('discovery.change_event'))

    def test_absent_inactive_or_fixture_accounts_are_not_granted(self):
        for name, active in [('inactive', False), ('a2-release-owner', True)]:
            user = get_user_model().objects.create_user(name, is_active=active)
            with self.assertRaises(CommandError): self.grant(name)
            self.assertFalse(user.user_permissions.exists())
        for name in ('', 'does-not-exist'):
            with self.assertRaises(CommandError): self.grant(name)
        self.assertFalse(get_user_model().objects.filter(username='does-not-exist').exists())
