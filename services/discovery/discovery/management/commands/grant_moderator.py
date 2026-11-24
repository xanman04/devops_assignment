"""Explicit operator command: grant only the selected existing account review permissions."""
import json
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

PERMISSIONS = ('change_venue', 'change_eventreport', 'hide_reported_event')


class Command(BaseCommand):
    help = 'Grant three Discovery review permissions to an explicitly selected existing account.'

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get('MODERATOR_USERNAME', '')
        if not username or len(username) > 150 or username.startswith('a2-release-'):
            raise CommandError('Choose an existing non-fixture Bassline username.')
        try:
            user = get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist:
            raise CommandError('That Bassline account does not exist. Register it first; no account or password was created.') from None
        if not user.is_active:
            raise CommandError('Refusing an inactive account.')
        permissions = [Permission.objects.get(content_type__app_label='discovery', codename=name) for name in PERMISSIONS]
        user.user_permissions.add(*permissions)
        self.stdout.write(json.dumps({'username': user.username, 'granted': list(PERMISSIONS),
                                     'password_and_account_flags_unchanged': True}))
