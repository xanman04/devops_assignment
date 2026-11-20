"""One-time own-student-subscription setup. No service/database provisioning here."""
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import uuid
from azure_preflight import azure_cli, run as preflight

PROVIDERS = ('Microsoft.App', 'Microsoft.OperationalInsights', 'Microsoft.Sql', 'Microsoft.Storage', 'Microsoft.ManagedIdentity')
READERS = ('amartini@faculty.ie.edu', 'bserra@faculty.ie.edu')


def command(argv, *, data=None, json_output=True):
    # Azure CLI uses Python and otherwise emits the Windows console code page.
    # Directory display names may contain accented characters even with JSON output.
    environment = dict(os.environ, PYTHONIOENCODING='utf-8')
    result = subprocess.run(argv, input=data, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', env=environment)
    if result.returncode:
        # Never echo argv/input/stdout: setup sends generated values through stdin.
        raise RuntimeError(f'{argv[0]} {argv[1]} failed (exit {result.returncode}). No secret values are printed; inspect the scoped resource in Azure.')
    return json.loads(result.stdout) if json_output and result.stdout.strip() else None


def az(*arguments):
    return command([azure_cli(), *arguments, '--output', 'json', '--only-show-errors'])


def names(student):
    if not re.fullmatch(r'[a-z][a-z0-9.-]{2,19}', student):
        raise ValueError('Use the IE email local-part, without @student.ie.edu.')
    prefix = student.replace('.', '-')
    return prefix, 'rg-'+prefix, prefix.replace('-', '')+'ui'


def role(principal, scope, role_name, principal_type='User'):
    existing = az('role', 'assignment', 'list', '--scope', scope)
    matches = [r for r in existing if r.get('principalId', '').lower() == principal.lower()
               and r.get('roleDefinitionName') == role_name and r.get('scope', '').lower() == scope.lower()]
    if not matches:
        az('role', 'assignment', 'create', '--assignee-object-id', principal,
           '--assignee-principal-type', principal_type, '--role', role_name, '--scope', scope)


def setup(args):
    uuid.UUID(args.subscription)
    prefix, group, storage = names(args.student)
    report = preflight(args.subscription)
    if 'student' not in (report.get('quota_id') or '').lower():
        raise RuntimeError('The subscription offer is not confirmed as Azure for Students. Check/activate the student offer before setup.')
    allowed = report['allowed_regions']
    if args.region not in allowed or args.sql_region not in allowed:
        raise RuntimeError('Both selected regions must appear in the subscription policy intersection.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        raise ValueError('Expected owner/repository.')
    gh = shutil.which('gh')
    if not gh:
        raise RuntimeError('GitHub CLI is required; sign in with gh auth login first.')
    repository = command([gh, 'api', 'repos/'+args.repo])
    if repository['full_name'].lower() != args.repo.lower():
        raise RuntimeError('Repository redirects must be resolved explicitly before setup.')
    az('account', 'set', '--subscription', args.subscription)
    for provider in PROVIDERS:
        az('provider', 'register', '--namespace', provider, '--wait')
    groups = az('group', 'list', '--subscription', args.subscription)
    existing = next((g for g in groups if g['name'].lower() == group), None)
    if existing and (existing.get('tags') or {}).get('owner') != prefix:
        raise RuntimeError('Existing group has no matching ownership tag. Refusing to adopt or alter it.')
    if not existing:
        az('group', 'create', '--name', group, '--location', args.region, '--tags', 'owner='+prefix, 'assignment=bassline-2')
    group_id = f'/subscriptions/{args.subscription}/resourceGroups/{group}'
    resources = az('resource', 'list', '--resource-group', group)
    if any(not r['name'].startswith(prefix) and r['name'] != storage for r in resources):
        raise RuntimeError('Unexpected resource names in the own group. Inspect before proceeding.')
    if not any(r['name'] == storage for r in resources):
        az('storage', 'account', 'create', '--name', storage, '--resource-group', group,
           '--location', args.region, '--sku', 'Standard_LRS', '--kind', 'StorageV2',
           '--min-tls-version', 'TLS1_2', '--allow-blob-public-access', 'false', '--allow-shared-key-access', 'false',
           '--tags', 'owner='+prefix, 'assignment=bassline-2')
    account = az('storage', 'account', 'show', '--name', storage, '--resource-group', group)
    validate_storage(account, prefix)
    identity = az('identity', 'create', '--name', prefix+'-github', '--resource-group', group,
                  '--location', args.region, '--tags', 'owner='+prefix, 'assignment=bassline-2')
    storage_id = group_id+'/providers/Microsoft.Storage/storageAccounts/'+storage
    role(identity['principalId'], group_id, 'Contributor', 'ServicePrincipal')
    role(identity['principalId'], storage_id, 'Storage Blob Data Contributor', 'ServicePrincipal')
    # The interactive owner also needs data-plane rights when shared keys are disabled.
    person = az('ad', 'signed-in-user', 'show')
    role(person['id'], storage_id, 'Storage Blob Data Contributor')
    for reader in READERS:
        user = az('ad', 'user', 'show', '--id', reader)
        role(user['id'], group_id, 'Reader')
    subjects = {
        prefix+'-main': f"repo:{repository['full_name']}:ref:refs/heads/main",
        prefix+'-main-ids': f"repo:{repository['owner']['login']}@{repository['owner']['id']}/{repository['name']}@{repository['id']}:ref:refs/heads/main",
    }
    credentials = az('identity', 'federated-credential', 'list', '--identity-name', prefix+'-github', '--resource-group', group)
    for name, subject in subjects.items():
        previous = next((c for c in credentials if c['name'] == name), None)
        if previous:
            if (previous.get('subject') != subject or previous.get('issuer') != 'https://token.actions.githubusercontent.com'
                    or previous.get('audiences') != ['api://AzureADTokenExchange']):
                raise RuntimeError('Existing federated identity differs. Inspect before changing its trust.')
            continue
        az('identity', 'federated-credential', 'create', '--name', name,
           '--identity-name', prefix+'-github', '--resource-group', group,
           '--issuer', 'https://token.actions.githubusercontent.com', '--subject', subject,
           '--audiences', 'api://AzureADTokenExchange')
    # Data-plane roles may take several minutes to propagate. A failed step is
    # safe to rerun; existing generated GitHub passwords are never overwritten.
    az('storage', 'blob', 'service-properties', 'update', '--account-name', storage,
       '--auth-mode', 'login', '--static-website', '--index-document', 'index.html')
    az('storage', 'container', 'create', '--account-name', storage, '--name', prefix+'-tfstate',
       '--public-access', 'off', '--auth-mode', 'login')
    container = az('storage', 'container', 'show', '--account-name', storage,
                   '--name', prefix+'-tfstate', '--auth-mode', 'login')
    if container.get('properties', {}).get('publicAccess') not in (None, 'off'):
        raise RuntimeError('Terraform state container is not private. Refusing to enable deployment.')
    present = command([gh, 'secret', 'list', '--repo', args.repo, '--json', 'name'])
    existing_names = {s['name'] for s in present}
    values = {'AZURE_CLIENT_ID': identity['clientId'], 'AZURE_TENANT_ID': identity['tenantId'],
              'AZURE_SUBSCRIPTION_ID': args.subscription}
    for name in ('SQL_ADMIN_PASSWORD', 'DISCOVERY_DB_PASSWORD', 'GROUPS_DB_PASSWORD', 'DISCOVERY_SECRET_KEY', 'GROUPS_SECRET_KEY'):
        if name not in existing_names:
            values[name] = 'Aa1!'+secrets.token_urlsafe(36)
    for name, value in values.items():
        command([gh, 'secret', 'set', name, '--repo', args.repo], data=value, json_output=False)
    variables = {'PREFIX': prefix, 'RESOURCE_GROUP': group, 'UI_STORAGE': storage,
                 'AZURE_REGION': args.region, 'AZURE_SQL_REGION': args.sql_region,
                 'AZURE_DEPLOYMENT_READY': 'true'}
    for name, value in variables.items():
        command([gh, 'variable', 'set', name, '--repo', args.repo, '--body', value], json_output=False)
    return {'resource_group': group, 'ui_storage': storage,
            'next': 'Run the main deployment workflow. It provisions SQL/apps, initializes contained users and deploys the tested images. No passwords were printed.'}


def validate_storage(account, prefix):
    if ((account.get('tags') or {}).get('owner') != prefix
            or account.get('allowBlobPublicAccess') is not False
            or account.get('allowSharedKeyAccess') is not False
            or account.get('kind') != 'StorageV2'
            or account.get('sku', {}).get('name') != 'Standard_LRS'):
        raise RuntimeError('Existing UI/state storage ownership, privacy or tier differs from the contract; inspect before proceeding.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('subscription', 'student', 'repo', 'region', 'sql-region'):
        parser.add_argument('--'+name, required=True)
    arguments = parser.parse_args()
    try:
        print(json.dumps(setup(arguments), indent=2))
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
