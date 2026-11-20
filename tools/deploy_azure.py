"""Deployment orchestration after same-commit CI. Requires scoped OIDC login."""
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from azure_bootstrap import az
from deployment_guard import validate

ROOT = Path(__file__).resolve().parents[1]


def execute(arguments, *, capture=False):
    result = subprocess.run(arguments, cwd=ROOT, text=True, capture_output=capture, check=False)
    if result.returncode:
        raise RuntimeError('Deployment command failed; inspect its masked pipeline output.')
    return result.stdout if capture else None


def terraform(*arguments, capture=False):
    return execute(['terraform', '-chdir=infra', *arguments], capture=capture)


def apply(bootstrap):
    destination = str(Path(os.environ['RUNNER_TEMP'])/'bassline-runtime.tfplan')
    try:
        terraform('plan', '-input=false', '-lock-timeout=5m', '-out='+destination,
                  '-var=bootstrap_mode='+str(bootstrap).lower())
        plan = json.loads(terraform('show', '-json', destination, capture=True))
        validate(plan, os.environ['PREFIX'])
        terraform('apply', '-input=false', '-lock-timeout=5m', destination)
    finally:
        Path(destination).unlink(missing_ok=True)


def health(urls, sha):
    deadline = time.monotonic()+480
    pending = dict(urls)
    while pending and time.monotonic() < deadline:
        for name, url in list(pending.items()):
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                break
            try:
                with urlopen(url+'/health', timeout=min(20, remaining)) as response:
                    body = json.load(response)
                    if response.status == 200 and body.get('db') == 'ok' and body.get('version') == sha:
                        pending.pop(name)
                        print(name+': healthy at the tested SHA.')
            except (HTTPError, URLError, OSError, ValueError):
                pass
        if pending:
            time.sleep(min(10, max(0, deadline-time.monotonic())))
    if pending:
        raise RuntimeError('Health/version deadline exceeded for '+', '.join(sorted(pending)))


def run():
    prefix = os.environ['PREFIX']
    group = os.environ['RESOURCE_GROUP']
    storage = os.environ['UI_STORAGE']
    sha = os.environ['GITHUB_SHA']
    if group != 'rg-'+prefix or storage != prefix.replace('-', '')+'ui' or not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Deployment identity/naming/SHA configuration is inconsistent.')
    terraform('init', '-input=false', '-lock-timeout=5m', '-lockfile=readonly',
        '-backend-config=resource_group_name='+group, '-backend-config=storage_account_name='+storage,
        '-backend-config=container_name='+prefix+'-tfstate', '-backend-config=key=runtime.tfstate',
        '-backend-config=use_oidc=true', '-backend-config=use_azuread_auth=true')
    apps = az('containerapp', 'list', '--resource-group', group)
    expected = {prefix+'-discovery', prefix+'-groups'}
    own = [a for a in apps if a['name'].startswith(prefix+'-')]
    if any(a['name'] not in expected for a in own):
        raise RuntimeError('Unexpected own-prefix app would violate the two-app allowance.')
    initializing = len(own) < 2 or any('mcr.microsoft.com/k8se/quickstart:latest' in json.dumps(a.get('properties', {}).get('template', {})) for a in own)
    if initializing:
        apply(True)
        host = json.loads(terraform('output', '-json', 'sql_host', capture=True))
        rule = prefix+'-initial-runner'
        with urlopen('https://api.ipify.org', timeout=15) as response:
            address = response.read(80).decode().strip()
        import ipaddress
        ipaddress.ip_address(address)
        try:
            az('sql', 'server', 'firewall-rule', 'create', '--resource-group', group,
               '--server', prefix+'-sql', '--name', rule, '--start-ip-address', address, '--end-ip-address', address)
            environment = dict(os.environ, SQL_HOST=host)
            image = os.environ['TF_VAR_image_namespace']+'/bassline-discovery:'+sha
            command = ['docker', 'run', '--rm', '-i']
            for name in ('PREFIX', 'SQL_HOST', 'SQL_ADMIN_PASSWORD', 'DISCOVERY_DB_PASSWORD', 'GROUPS_DB_PASSWORD'):
                command.extend(['-e', name])
            command.extend([image, 'python', '-'])
            with (ROOT/'tools/initialize_azure_sql.py').open(encoding='utf-8') as script:
                result = subprocess.run(command, input=script.read(), text=True, env=environment)
            if result.returncode:
                raise RuntimeError('Contained SQL identity initialization failed; credentials withheld.')
        finally:
            az('sql', 'server', 'firewall-rule', 'delete', '--resource-group', group,
               '--server', prefix+'-sql', '--name', rule)
    apply(False)
    urls = json.loads(terraform('output', '-json', 'service_urls', capture=True))
    config = ROOT/'ui/config.js'
    config.write_text('window.BASSLINE_CONFIG = '+json.dumps({name+'Url': url for name, url in urls.items()})+';\n', encoding='utf-8')
    # Publish a prepared folder, excluding operator docs, nginx and source templates.
    import shutil
    destination = Path(os.environ['RUNNER_TEMP'])/'bassline-public-ui'
    destination.mkdir(exist_ok=True)
    for source in (ROOT/'ui').iterdir():
        if source.name in {'README.md', 'nginx.conf', 'config.js.template'}:
            continue
        if source.is_dir():
            shutil.copytree(source, destination/source.name, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination/source.name)
    az('storage', 'blob', 'upload-batch', '--account-name', storage, '--auth-mode', 'login',
       '--destination', '$web', '--source', str(destination), '--overwrite', 'true')
    health(urls, sha)
    public_url = json.loads(terraform('output', '-json', 'public_url', capture=True))
    print('Public UI: '+public_url)
    with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as summary:
        summary.write(f'### Deployed Bassline\n\nSHA: `{sha}`\n\nUI: {public_url}\n\nBoth services reported healthy own databases and this exact version.\n')


if __name__ == '__main__':
    run()
