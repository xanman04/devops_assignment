"""Real browser + two real HTTP services, isolated SQLite fixtures; no user data."""
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading

from check_service_boundary import free_port, wait_health

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory(prefix='bassline-browser-') as directory:
        workspace = Path(directory)
        processes = []
        handles = []
        urls = {name: f'http://localhost:{free_port()}' for name in ('discovery', 'groups', 'ui')}
        password = secrets.token_urlsafe(24)
        environments = {}
        try:
            for name in ('discovery', 'groups'):
                env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.settings',
                    DJANGO_SECRET_KEY=secrets.token_urlsafe(48), PORT=urls[name].split(':')[-1],
                    DATABASE_URL='sqlite:///' + str(workspace / (name+'.sqlite3')),
                    DISCOVERY_URL=urls['discovery'], UI_ORIGIN=urls['ui'], SEED_TAXONOMY='1' if name == 'discovery' else '0')
                environments[name] = env
                output = (workspace / (name+'.log')).open('w', encoding='utf-8')
                handles.append(output)
                process = subprocess.Popen([sys.executable, '-u', 'serve.py'], cwd=ROOT/'services'/name,
                    env=env, stdout=output, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                processes.append(process)
                wait_health(urls[name], process)
            fixture = '''
import os, django
django.setup()
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from discovery import services
from discovery.models import GenreCategory
owner=get_user_model().objects.create_superuser('browserowner', password=os.environ['BROWSER_PASSWORD'])
guest=get_user_model().objects.create_user('browserguest', password=os.environ['BROWSER_PASSWORD'])
category=GenreCategory.objects.get(name='House')
venue=services.save_venue(actor=owner,review_status='approved',data={'name':'Browser venue','address':'Madrid','latitude':'40.416800','longitude':'-3.703800','timezone':'Europe/Madrid'})
start=timezone.now()+timedelta(days=2)
event=services.save_event(actor=owner,category_ids=[category.pk],data={'venue':venue,'title':'Browser <img src=x onerror=alert(1)> night','description':'Safe fixture description','starts_at':start,'ends_at':start+timedelta(hours=4)})
event.demo_poster='demo-posters/blue-hour.webp'
event.save(update_fields=['demo_poster'])
services.save_venue(actor=guest,data={'name':'Review <img src=x onerror=alert(1)> venue','address':'Madrid','latitude':'40.4','longitude':'-3.7','timezone':'Europe/Madrid'})
services.report_event(actor=guest,event_id=event.pk,reason='other',explanation='Review <script>alert(1)</script> safely as text')
'''
            subprocess.run([sys.executable, '-c', fixture], cwd=ROOT/'services'/'discovery',
                env=dict(environments['discovery'], BROWSER_PASSWORD=password), check=True)

            class Handler(SimpleHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/config.js':
                        payload = ('window.BASSLINE_CONFIG='+json.dumps({name+'Url': urls[name] for name in ('discovery', 'groups')})+';').encode()
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/javascript')
                        self.send_header('Content-Length', str(len(payload)))
                        self.end_headers()
                        self.wfile.write(payload)
                    else:
                        super().do_GET()

                def log_message(self, *_):
                    pass

            server = ThreadingHTTPServer(('localhost', int(urls['ui'].split(':')[-1])),
                functools.partial(Handler, directory=str(ROOT/'ui')))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                subprocess.run(['node', str(ROOT/'tools/browser/check.cjs')], cwd=ROOT,
                    env=dict(os.environ, BROWSER_UI_URL=urls['ui'], BROWSER_DISCOVERY_URL=urls['discovery'],
                             BROWSER_GROUPS_URL=urls['groups'], BROWSER_PASSWORD=password), check=True)
            finally:
                server.shutdown()
                server.server_close()
        except Exception:
            # Logs contain paths/status/timings, never request payloads or bearer credentials.
            for name in ('discovery', 'groups'):
                path = workspace / (name+'.log')
                if path.exists():
                    print(path.read_text(encoding='utf-8')[-5000:], file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                if os.name == 'nt':
                    # The Windows venv launcher owns a Python child; terminate this
                    # check's entire process tree before closing its log files.
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                else:
                    process.terminate()
                process.wait(timeout=15)
            for handle in handles:
                handle.close()


if __name__ == '__main__':
    run()
