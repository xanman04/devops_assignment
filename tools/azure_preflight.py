"""Read-only subscription/region check. Never logs in or creates resources."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def azure_cli():
    command = shutil.which('az')
    if command:
        return command
    for base in ('ProgramFiles', 'ProgramFiles(x86)'):
        candidate = Path(os.environ.get(base, 'C:/Program Files'))/'Microsoft SDKs/Azure/CLI2/wbin/az.cmd'
        if candidate.exists():
            return str(candidate)
    raise RuntimeError('Azure CLI is missing. Install Microsoft.AzureCLI and reopen your terminal.')


def read(*arguments):
    result = subprocess.run([azure_cli(), *arguments, '--output', 'json', '--only-show-errors'],
        text=True, capture_output=True, encoding='utf-8')
    if result.returncode:
        # Account/policy commands return metadata only; never request access tokens.
        raise RuntimeError('Azure account/policy read failed. Sign in with az login --use-device-code and check the selected tenant.')
    return json.loads(result.stdout)


def region_lists(assignments):
    """Intersect all allowed-location assignments; no guessed default region."""
    lists = []
    for assignment in assignments:
        properties = assignment.get('properties', assignment)
        title = properties.get('displayName', '').lower()
        parameters = properties.get('parameters', {})
        candidates = [value.get('value') for key, value in parameters.items()
                      if 'allowed' in key.lower() and ('location' in key.lower() or 'region' in key.lower())]
        if 'allowed' in title and ('region' in title or 'location' in title):
            candidates.extend(v.get('value') for v in parameters.values())
        for values in candidates:
            if isinstance(values, list) and values and all(isinstance(v, str) for v in values):
                lists.append({v.lower().replace(' ', '') for v in values})
    return sorted(set.intersection(*lists)) if lists else []


def run(subscription=None):
    accounts = read('account', 'list', '--all')
    if not accounts:
        raise RuntimeError('No signed-in subscriptions. Run az login --use-device-code with your IE account first.')
    metadata = [{'name': a['name'], 'id': a['id'], 'state': a['state'],
                 'tenant_id': a['tenantId']} for a in accounts]
    if subscription is None:
        return {'subscriptions': metadata,
            'next_step': 'Confirm the active Azure for Students subscription ID, then rerun with --subscription ID. A custom name or IE tenant alone does not prove the offer.'}
    uuid.UUID(subscription)
    account = next((a for a in accounts if a['id'].lower() == subscription.lower()), None)
    if account is None or account['state'].lower() != 'enabled':
        raise RuntimeError('The selected subscription is not present and Enabled in this login. No resources were changed.')
    details = read('rest', '--method', 'get', '--url',
        f'https://management.azure.com/subscriptions/{subscription}?api-version=2022-12-01',
        '--subscription', subscription)
    policies = read('policy', 'assignment', 'list', '--scope', f'/subscriptions/{subscription}',
                    '--disable-scope-strict-match', 'true', '--subscription', subscription)
    regions = region_lists(policies)
    return {'subscription': next(a for a in metadata if a['id'].lower() == subscription.lower()),
        'quota_id': details.get('subscriptionPolicies', {}).get('quotaId'),
        'allowed_regions': regions,
        'ready_to_choose_region': bool(regions),
        'warning': 'This is read-only. Verify Azure for Students and free SQL availability before bootstrap. An empty region list needs policy inspection; never guess.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subscription')
    arguments = parser.parse_args()
    try:
        print(json.dumps(run(arguments.subscription), indent=2))
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
