"""Verify the source export and both imports using disposable SQLite databases."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def execute(folder, environment, *arguments):
    return subprocess.run([sys.executable, *arguments], cwd=folder, env=environment,
                          check=True, text=True, capture_output=True, timeout=90).stdout


def run():
    with tempfile.TemporaryDirectory(prefix='bassline-split-import-') as directory:
        temp = Path(directory)
        environment = os.environ.copy()
        environment.update(DJANGO_SECRET_KEY=secrets.token_urlsafe(48), DATA_DIR=str(temp/'source'),
                           DJANGO_SETTINGS_MODULE='config.settings', IMPORT_TEST_PASSWORD=secrets.token_urlsafe(24))
        environment.pop('SQLSERVER_TEST_MODE', None)
        export = temp/'source/split.json'
        environment['IMPORT_TEST_EXPORT'] = str(export)
        execute(ROOT, environment, 'manage.py', 'migrate', '--noinput')
        source = '''
import io, os, json, django
django.setup()
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.utils import timezone
from discovery import services as discovery
from groups import services as groups
owner=get_user_model().objects.create_superuser('import-owner', password=os.environ['IMPORT_TEST_PASSWORD'])
guest=get_user_model().objects.create_user('import-guest', password=os.environ['IMPORT_TEST_PASSWORD'])
role=Group.objects.create(name='Imported group moderator')
role.permissions.add(Permission.objects.get(content_type__app_label='groups',codename='change_attendancegroup'))
guest.groups.add(role)
category=discovery.save_category(actor=owner,data={'name':'House','color':'#123456','description':'Test'})
venue=discovery.save_venue(actor=owner,review_status='approved',data={'name':'Venue','latitude':48,'longitude':2,'timezone':'Europe/Paris'})
start=timezone.now()+timedelta(days=2)
event=discovery.save_event(actor=owner,category_ids=[category.pk],data={'venue':venue,'title':'Import event','description':'Test','starts_at':start,'ends_at':start+timedelta(hours=4)})
LogEntry.objects.create(user=owner, content_type=ContentType.objects.get_for_model(event), object_id=str(event.pk), object_repr='Import event', action_flag=1, change_message='Created')
group=groups.save_group(actor=owner,data={'event':event,'name':'Import group','description':'Test','capacity':4,'joining_mode':'public'})
groups.join_group(actor=guest,group_id=group.pk)
groups.post_message(actor=guest,group_id=group.pk,body='Retained conversation')
groups.leave_group(actor=owner,group_id=group.pk)
discovery.follow_event(actor=owner,event_id=event.pk)
discovery.save_event(actor=owner,event_id=event.pk,category_ids=[category.pk],data={'starts_at':start+timedelta(hours=1)})
call_command('export_split_data',os.environ['IMPORT_TEST_EXPORT'],stdout=io.StringIO())
print(json.dumps({'owner':owner.pk,'guest':guest.pk,'event':event.pk,'group':group.pk}))
'''
        ids = json.loads(execute(ROOT, environment, '-c', source))
        for owner in ('discovery', 'groups'):
            target_environment = environment.copy()
            target_environment['DATABASE_URL'] = 'sqlite:///'+str(temp/(owner+'.sqlite3'))
            folder = ROOT/'services'/owner
            execute(folder, target_environment, 'manage.py', 'migrate', '--noinput')
            execute(folder, target_environment, 'manage.py', 'import_split_data', str(export))
            repeat = execute(folder, target_environment, 'manage.py', 'import_split_data', str(export))
            assert 'already imported' in repeat
            if owner == 'discovery':
                check = f'''
import django,os
django.setup()
from django.contrib.auth import get_user_model
from discovery.models import Event, LegacyAdminAudit
from notifications.models import Notification
user=get_user_model().objects.get(pk={ids['guest']})
assert user.check_password(os.environ['IMPORT_TEST_PASSWORD'])
assert user.has_perm('groups.change_attendancegroup')
assert Event.objects.get(pk={ids['event']}).creator_id == {ids['owner']}
assert LegacyAdminAudit.objects.get().user_id == {ids['owner']}
assert Notification.objects.filter(recipient_id={ids['owner']}).count() == 1
'''
            else:
                check = f'''
import django
django.setup()
from groups.models import AttendanceGroup,Membership,Message,Person
from notifications.models import Notification
group=AttendanceGroup.objects.get(pk={ids['group']})
assert group.owner_id == {ids['guest']} and group.event_id == {ids['event']}
assert Membership.objects.get(group=group).user_id == {ids['guest']}
assert Message.objects.get(group=group).body == 'Retained conversation'
assert Notification.objects.filter(recipient_id={ids['guest']}).count() == 1
assert 'password' not in {{field.name for field in Person._meta.fields}}
'''
            execute(folder, target_environment, '-c', check)
        print('PASS: stable IDs, Discovery passwords/roles, Groups chat/notifications and repeat import.')


if __name__ == '__main__':
    run()
