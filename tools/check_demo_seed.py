"""Run the demo seeding twice against two real services on disposable SQLite databases."""
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from check_service_boundary import free_port, request, wait_health
import seed_demo_groups

ROOT = Path(__file__).resolve().parents[1]


def run():
    with tempfile.TemporaryDirectory(prefix='bassline-demo-') as directory:
        workspace = Path(directory)
        urls = {name: f'http://localhost:{free_port()}' for name in ('discovery', 'groups')}
        password = secrets.token_urlsafe(24)
        processes, handles, environments = [], [], {}
        try:
            for name in ('discovery', 'groups'):
                env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.settings',
                           DJANGO_SECRET_KEY=secrets.token_urlsafe(48), PORT=urls[name].split(':')[-1],
                           DATABASE_URL='sqlite:///' + str(workspace / (name + '.sqlite3')),
                           DISCOVERY_URL=urls['discovery'], DISCOVERY_TIMEOUT_S='15',
                           SEED_TAXONOMY='1' if name == 'discovery' else '0')
                environments[name] = env
                handle = (workspace / (name + '.log')).open('w', encoding='utf-8')
                handles.append(handle)
                process = subprocess.Popen([sys.executable, '-u', 'serve.py'], cwd=ROOT / 'services' / name, env=env,
                    stdout=handle, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                processes.append(process)
                wait_health(urls[name], process)
            results = []
            for arguments in ((), ('--refresh-dates',)):
                subprocess.run([sys.executable, 'manage.py', 'seed_demo_content', *arguments],
                    cwd=ROOT / 'services' / 'discovery', check=True, stdout=subprocess.DEVNULL,
                    env=dict(environments['discovery'], DEMO_ACCOUNT_PASSWORD=password))
                results.append(seed_demo_groups.seed(urls['discovery'], urls['groups'], password))
            first, second = results
            assert first == second, (first, second)
            solo, family = first
            assert (solo['members'], solo['messages'], solo['active_bans']) == (4, 5, 0), solo
            assert (family['members'], family['messages'], family['active_bans']) == (6, 0, 1), family
            status, listed = request(urls['groups'], f"/api/events/{family['event_id']}/groups/")
            assert status == 200 and [g['name'] for g in listed['groups']] == ['Smith Family'], listed
            print('PASS: demo accounts, events and groups load through the real services and repeat without duplicates.')
        except Exception:
            for name in ('discovery', 'groups'):
                log = workspace / (name + '.log')
                if log.exists():
                    print(log.read_text(encoding='utf-8')[-4000:], file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                else:
                    process.terminate()
                process.wait(timeout=15)
            for handle in handles:
                handle.close()


if __name__ == '__main__':
    run()
