"""Run both actual service processes against disposable local databases.

Invoked by CI after unit tests. Requires loopback socket permissions. Never
uses Azure, existing application data or saved user credentials.
"""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        return server.getsockname()[1]


def request(base, path, data=None, token=None, key=None):
    headers = {'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer '+token
    if key:
        headers['Idempotency-Key'] = key
    payload = None
    if data is not None:
        payload = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    try:
        with urlopen(Request(base+path, data=payload, headers=headers), timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read())


def wait_health(base, process):
    deadline = time.monotonic()+45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError('Service exited before becoming healthy.')
        try:
            status, _ = request(base, '/health')
            if status == 200:
                return
        except (URLError, TimeoutError, OSError):
            pass
        time.sleep(.2)
    raise RuntimeError('Service startup exceeded 45 seconds.')


def run():
    with tempfile.TemporaryDirectory(prefix='bassline-boundary-') as directory:
        workspace = Path(directory)
        environments, urls = {}, {}
        password = secrets.token_urlsafe(24)
        ports = {'discovery': free_port(), 'groups': free_port()}
        while ports['groups'] == ports['discovery']:
            ports['groups'] = free_port()
        for name in ports:
            environment = os.environ.copy()
            environment.update(DJANGO_SETTINGS_MODULE='config.settings',
                DJANGO_SECRET_KEY=secrets.token_urlsafe(48), PORT=str(ports[name]),
                DATABASE_URL='sqlite:///'+str(workspace/(name+'.sqlite3')),
                VERSION='boundary-smoke', SMOKE_PASSWORD=password)
            environments[name] = environment
            urls[name] = f'http://127.0.0.1:{ports[name]}'
        environments['groups']['DISCOVERY_URL'] = urls['discovery']
        processes, handles = {}, []

        def start(name, suffix=''):
            output = (workspace/(name+suffix+'.log')).open('w', encoding='utf-8')
            handles.append(output)
            process = subprocess.Popen([sys.executable, '-u', 'serve.py'],
                cwd=ROOT/'services'/name, env=environments[name], stdout=output,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            processes[name] = process
            wait_health(urls[name], process)

        try:
            start('discovery')
            start('groups')
            setup = '''
import os, json, django
django.setup()
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from discovery import services
owner=get_user_model().objects.create_superuser('smokeowner', password=os.environ['SMOKE_PASSWORD'])
get_user_model().objects.create_user('smokeguest', password=os.environ['SMOKE_PASSWORD'])
category=services.save_category(actor=owner, data={'name':'House','color':'#123456','description':'Test'})
venue=services.save_venue(actor=owner, review_status='approved', data={'name':'Test venue','latitude':48,'longitude':2,'timezone':'Europe/Paris'})
start=timezone.now()+timedelta(days=2)
event=services.save_event(actor=owner,category_ids=[category.pk],data={'venue':venue,'title':'Test event','description':'Test','starts_at':start,'ends_at':start+timedelta(hours=4)})
print(json.dumps({'event_id':event.pk}))
'''
            result = subprocess.run([sys.executable, '-c', setup], cwd=ROOT/'services/discovery',
                env=environments['discovery'], check=True, capture_output=True, text=True, timeout=30)
            event_id = json.loads(result.stdout)['event_id']
            credentials = {}
            for name in ('smokeowner', 'smokeguest'):
                status, result = request(urls['discovery'], '/api/auth/token/', {'username': name, 'password': password})
                assert status == 200, status
                credentials[name] = result['token']
            data = {'event_id': event_id, 'name': 'Test group', 'description': 'Integration test',
                    'capacity': 4, 'joining_mode': 'public'}
            status, group = request(urls['groups'], '/api/groups/', data, credentials['smokeowner'], 'create-once')
            assert status == 201, (status, group)
            status, _ = request(urls['groups'], f"/api/groups/{group['id']}/join/", {}, credentials['smokeguest'])
            assert status == 200, status
            status, _ = request(urls['groups'], f"/api/groups/{group['id']}/messages/", {'body': 'Hello'}, credentials['smokeguest'])
            assert status == 201, status
            status, chat = request(urls['groups'], f"/api/groups/{group['id']}/chat/", token=credentials['smokeguest'])
            assert status == 200 and len(chat['members']) == 2 and len(chat['messages']) == 1, status
            processes['discovery'].terminate()
            processes['discovery'].wait(timeout=10)
            assert request(urls['groups'], '/health')[0] == 200
            status, groups = request(urls['groups'], f'/api/events/{event_id}/groups/')
            assert status == 200 and len(groups['groups']) == 1
            assert request(urls['groups'], f"/api/groups/{group['id']}/join/", {}, credentials['smokeguest'])[0] == 503
            start('discovery', '-restart')
            status, replay = request(urls['groups'], '/api/groups/', data, credentials['smokeowner'], 'create-once')
            assert status == 201 and replay['id'] == group['id'], (status, replay)
            print('PASS: real HTTP identity, event validation, create/join/chat, peer outage and restart/replay.')
        except Exception:
            for handle in handles:
                handle.flush()
            for log in workspace.glob('*.log'):
                print(log.name, log.read_text(encoding='utf-8'), file=sys.stderr)
            raise
        finally:
            for process in processes.values():
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            for handle in handles:
                handle.close()


if __name__ == '__main__':
    run()
