"""Explicit main-only release exercise. Never called by CI; no credentials in files."""
import argparse
from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import quote
from urllib.request import urlopen
import uuid

from azure_bootstrap import az
from deploy_azure import health

ROOT = Path(__file__).resolve().parents[1]
API = '2025-07-01'


def context():
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('GITHUB_REF') != 'refs/heads/main'
            or os.environ.get('GITHUB_REPOSITORY') != 'xanman04/devops_assignment'):
        raise ValueError('Release exercise is restricted to this repository main workflow.')
    prefix = os.environ['PREFIX']
    if not re.fullmatch(r'[a-z][a-z0-9-]{2,19}', prefix) or os.environ['RESOURCE_GROUP'] != 'rg-'+prefix:
        raise ValueError('Unexpected resource scope.')
    uuid.UUID(os.environ['ARM_SUBSCRIPTION_ID'])
    if not re.fullmatch(r'[0-9a-f]{40}', os.environ['GITHUB_SHA']):
        raise ValueError('Expected a full release SHA.')
    if not os.environ['GITHUB_RUN_ID'].isdigit():
        raise ValueError('Expected a workflow run ID.')
    return prefix, 'rg-'+prefix


def directory():
    context()
    result = Path(os.environ['RUNNER_TEMP'])/'bassline-live-evidence'
    result.mkdir(exist_ok=True)
    return result


def write(name, value):
    (directory()/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def read(name):
    return json.loads((directory()/name).read_text(encoding='utf-8'))


def endpoint(service):
    prefix, group = context()
    if service not in {'discovery', 'groups'}:
        raise ValueError('Unknown domain service.')
    return (f'https://management.azure.com/subscriptions/{os.environ["ARM_SUBSCRIPTION_ID"]}'
            f'/resourceGroups/{group}/providers/Microsoft.App/containerApps/{prefix}-{service}')


def running(service):
    app = az('rest', '--method', 'get', '--url', endpoint(service)+'?api-version='+API)
    return app['properties'].get('runningStatus')


def lifecycle(service, action):
    if action not in {'start', 'stop'}:
        raise ValueError('Only start/stop operations are permitted.')
    az('rest', '--method', 'post', '--url', endpoint(service)+'/'+action+'?api-version='+API)
    expected = 'Running' if action == 'start' else 'Stopped'
    deadline = time.monotonic()+180
    while time.monotonic() < deadline:
        if running(service) == expected:
            return
        time.sleep(5)
    raise RuntimeError('Container App lifecycle deadline exceeded.')


def ensure_running(service):
    # A timed-out stop may still be transitioning. Do not race it with start.
    deadline = time.monotonic()+240
    while time.monotonic() < deadline:
        status = running(service)
        if status == 'Running':
            return
        if status == 'Stopped':
            lifecycle(service, 'start')
            return
        time.sleep(5)
    raise RuntimeError('App did not settle into a recoverable lifecycle state.')


def prepare():
    prefix, group = context()
    # Main may advance while a queued dispatch waits: do not exercise stale images.
    head = subprocess.check_output(['gh', 'api', 'repos/xanman04/devops_assignment/git/ref/heads/main',
                                   '--jq', '.object.sha'], text=True).strip()
    if head != os.environ['GITHUB_SHA']:
        raise ValueError('Main advanced; dispatch verification for the current deployed main.')
    apps = az('containerapp', 'list', '--resource-group', group)
    urls = {}
    for service in ('discovery', 'groups'):
        matches = [a for a in apps if a['name'] == prefix+'-'+service]
        if len(matches) != 1:
            raise ValueError('Expected exactly the own named application.')
        app = matches[0]
        image = app['properties']['template']['containers'][0]['image']
        if image != f'ghcr.io/xanman04/bassline-{service}:'+head:
            raise ValueError('Application image does not match the dispatched main SHA.')
        host = app['properties']['configuration']['ingress']['fqdn']
        if not host.startswith(prefix+'-'+service+'.') or not host.endswith('.azurecontainerapps.io'):
            raise ValueError('Unexpected application host.')
        urls[service] = 'https://'+host
    health(urls, head)
    if any(running(s) != 'Running' for s in urls):
        raise ValueError('Both applications must initially be running.')
    storage = az('storage', 'account', 'show', '--resource-group', group, '--name', prefix.replace('-', '')+'ui')
    write('configuration.json', {'sha': head, 'urls': urls, 'ui': storage['primaryEndpoints']['web'],
                                'run_id': os.environ['GITHUB_RUN_ID']})
    if (directory()/'restore-required.json').exists() and read('restore-required.json'):
        raise ValueError('An earlier recovery obligation must be resolved first.')
    write('restore-required.json', [])
    rule = prefix+'-verify-'+os.environ['GITHUB_RUN_ID']
    write('firewall.json', {'rule': rule})
    try:
        with urlopen('https://api.ipify.org', timeout=15) as response:
            address = response.read(80).decode().strip()
        ipaddress.ip_address(address)
        az('sql', 'server', 'firewall-rule', 'create', '--resource-group', group, '--server', prefix+'-sql',
           '--name', rule, '--start-ip-address', address, '--end-ip-address', address)
        environment = dict(os.environ, DATABASE_URL=(
            f'mssql://bassline_discovery:{quote(os.environ["DISCOVERY_DB_PASSWORD"], safe="")}@'
            f'{prefix}-sql.database.windows.net:1433/{prefix}-discovery-db'))
        command = ['docker', 'run', '--rm']
        for name in ('DATABASE_URL', 'DJANGO_SECRET_KEY', 'LIVE_CHECK_PASSWORD'):
            command.extend(['-e', name])
        command.extend(['ghcr.io/xanman04/bassline-discovery:'+head, 'python', 'manage.py', 'prepare_live_check'])
        result = subprocess.run(command, env=environment, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Controlled fixture setup failed; database diagnostics withheld.')
        fixture = json.loads(result.stdout.strip().splitlines()[-1])
        write('fixture.json', fixture)
    finally:
        cleanup_firewall()
    audit_migration()


def audit_migration():
    config = read('configuration.json')
    before = json.loads((ROOT/'evidence/azure/2026-11-23-before-slug-migration.json').read_text(encoding='utf-8'))
    with urlopen(config['urls']['discovery']+'/api/genres/', timeout=30) as response:
        after = json.load(response)['categories']
    original = {row['id']: row['name'] for row in before['genre_categories']}
    if not original:
        raise ValueError('Before-migration evidence must contain populated rows.')
    current = {row['id']: row for row in after}
    if len(current) != len(after) or any(i not in current or current[i]['name'] != name for i, name in original.items()):
        raise ValueError('Previously populated category IDs/names were not preserved.')
    slugs = [row.get('slug') for row in after]
    if any(not isinstance(s, str) or not s for s in slugs) or len(set(slugs)) != len(slugs):
        raise ValueError('Backfilled slugs must be nonempty and unique.')
    records = read('fixture.json').get('migrations', [])
    if {row['name'] for row in records} != {'0014_genrecategory_slug', '0015_genrecategory_slug_unique'}:
        raise ValueError('Both applied migration records are required.')
    for record in records:
        datetime.fromisoformat(record['applied_at'])
    write('migration-audit.json', {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
          'sha': config['sha'], 'baseline': 'evidence/azure/2026-11-23-before-slug-migration.json',
          'preserved_categories': [{'id': i, 'name': name, 'slug': current[i]['slug']} for i, name in original.items()],
          'applied_records': records,
          'limit': 'Applied database records and public before/after rows; not an original startup console log.'})


def cleanup_firewall():
    prefix, group = context()
    path = directory()/'firewall.json'
    if path.exists():
        expected = prefix+'-verify-'+os.environ['GITHUB_RUN_ID']
        if read('firewall.json')['rule'] != expected:
            raise ValueError('Unexpected firewall recovery marker.')
        existing = az('sql', 'server', 'firewall-rule', 'list', '--resource-group', group, '--server', prefix+'-sql')
        if any(rule['name'] == expected for rule in existing):
            az('sql', 'server', 'firewall-rule', 'delete', '--resource-group', group,
               '--server', prefix+'-sql', '--name', expected)
        path.unlink()


def stop(service):
    endpoint(service)  # Validate before recording the recovery obligation.
    pending = read('restore-required.json')
    if pending:
        raise ValueError('Restore the previous domain before stopping another.')
    # Persist before the request, including the ambiguous accepted-but-client-failed case.
    write('restore-required.json', [service])
    lifecycle(service, 'stop')


def restore():
    path = directory()/'restore-required.json'
    errors = []
    if path.exists():
        pending = read('restore-required.json')
        for service in list(pending):
            try:
                endpoint(service)
                ensure_running(service)
                pending.remove(service)
                write('restore-required.json', pending)
            except Exception:
                errors.append(service)
    try:
        cleanup_firewall()
    except Exception:
        errors.append('temporary firewall')
    # Recovery deliberately does not require main still to equal the dispatched SHA.
    if (directory()/'configuration.json').exists():
        try:
            config = read('configuration.json')
            health(config['urls'], config['sha'])
        except Exception:
            errors.append('final health')
    if errors:
        raise RuntimeError('Recovery requires attention: '+', '.join(errors))


def recover_all():
    """Explicit recovery dispatch if a killed runner lost its private markers."""
    prefix, group = context()
    failures = []
    for service in ('discovery', 'groups'):
        try:
            app = az('containerapp', 'show', '--resource-group', group, '--name', prefix+'-'+service)
            image = app['properties']['template']['containers'][0]['image']
            expected = 'ghcr.io/xanman04/bassline-'+service+':'
            if not image.startswith(expected) or not re.fullmatch(r'[0-9a-f]{40}', image[len(expected):]):
                raise ValueError('Unexpected recovery image.')
            host = app['properties']['configuration']['ingress']['fqdn']
            if not host.startswith(prefix+'-'+service+'.') or not host.endswith('.azurecontainerapps.io'):
                raise ValueError('Unexpected recovery host.')
            ensure_running(service)
            health({service: 'https://'+host}, image[len(expected):])
        except Exception:
            failures.append(service)
    for rule in az('sql', 'server', 'firewall-rule', 'list', '--resource-group', group, '--server', prefix+'-sql'):
        if re.fullmatch(re.escape(prefix)+r'-verify-[0-9]+', rule['name']):
            az('sql', 'server', 'firewall-rule', 'delete', '--resource-group', group,
               '--server', prefix+'-sql', '--name', rule['name'])
    if failures:
        raise RuntimeError('Explicit recovery failed for '+', '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'stop', 'restore', 'recover'])
    parser.add_argument('service', nargs='?', choices=['discovery', 'groups'])
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    elif args.action == 'restore': restore()
    elif args.action == 'recover': recover_all()
    elif args.service: stop(args.service)
    else: parser.error('stop requires a service')
