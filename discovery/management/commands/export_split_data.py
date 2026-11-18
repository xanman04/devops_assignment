"""Read-only consistent export from Assignment 1 to the two service owners."""
import json
import os
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction


def records(queryset, *, natural=True, natural_primary=False):
    return serializers.serialize('python', queryset, use_natural_foreign_keys=natural,
                                 use_natural_primary_keys=natural_primary)


class Command(BaseCommand):
    help = 'Export existing data with stable IDs to a new sensitive file under data/.'

    def add_arguments(self, parser):
        parser.add_argument('output', type=Path)

    def handle(self, *args, **options):
        path = options['output'].resolve()
        if not path.is_relative_to(settings.DATA_DIR.resolve()):
            raise CommandError('Exports contain private data and password hashes; output must be under ignored data/.')
        if path.exists():
            raise CommandError('Refusing to overwrite an existing export.')
        payload = {'format': 1, 'discovery': [], 'groups': []}
        with transaction.atomic():
            for label in ('contenttypes.ContentType', 'auth.Permission', 'auth.Group'):
                payload['discovery'].extend(records(apps.get_model(label).objects.all(), natural_primary=True))
            payload['discovery'].extend(records(get_user_model().objects.all()))
            for model in apps.get_app_config('discovery').get_models():
                payload['discovery'].extend(records(model.objects.all()))
            for row in records(apps.get_model('admin.LogEntry').objects.all()):
                row['model'] = 'discovery.legacyadminaudit'
                payload['discovery'].append(row)
            payload['groups'].extend({'model': 'groups.person', 'pk': user.pk,
                'fields': {'display_name': user.public_name}} for user in get_user_model().objects.all())
            for model in apps.get_app_config('groups').get_models():
                rows = records(model.objects.all(), natural=False)
                if model._meta.model_name == 'attendancegroup':
                    events = {group.pk: group.event for group in model.objects.select_related('event')}
                    for row in rows:
                        event = events[row['pk']]
                        row['fields'].pop('event')
                        row['fields'].update(event_id=event.pk, event_title=event.title,
                                             event_starts_at=event.starts_at)
                if model._meta.model_name == 'membership':
                    events = dict(model.objects.values_list('pk', 'group__event_id'))
                    for row in rows:
                        row['fields']['event_id'] = events[row['pk']]
                payload['groups'].extend(rows)
            notification = apps.get_model('notifications.Notification')
            for owner, rows, remove in (
                ('discovery', records(notification.objects.filter(kind='event_change')), ('group', 'join_request')),
                ('groups', records(notification.objects.exclude(kind='event_change'), natural=False), ('event_change',)),
            ):
                for row in rows:
                    for field in remove:
                        row['fields'].pop(field)
                payload[owner].extend(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as output:
            json.dump(payload, output, cls=DjangoJSONEncoder)
        self.stdout.write('Export created. It contains private records/password hashes; never commit or publish it.')
