"""Reject destructive/out-of-scope Terraform plans; never print plan secrets."""
import json
import sys


def validate(plan, prefix):
    expected = 'rg-'+prefix
    allowed_types = {'azurerm_log_analytics_workspace', 'azurerm_container_app_environment',
                     'azurerm_mssql_server', 'azurerm_mssql_firewall_rule',
                     'azurerm_container_app', 'azapi_resource'}
    names = {
        'azurerm_log_analytics_workspace': {prefix+'-logs'},
        'azurerm_container_app_environment': {prefix+'-env'},
        'azurerm_mssql_server': {prefix+'-sql'},
        'azurerm_mssql_firewall_rule': {prefix+'-azure-services'},
        'azurerm_container_app': {prefix+'-discovery', prefix+'-groups'},
        'azapi_resource': {prefix+'-discovery-db', prefix+'-groups-db'},
    }
    seen = set()
    for change in plan.get('resource_changes', []):
        if change.get('mode') == 'data':
            continue
        if 'delete' in change['change']['actions']:
            raise ValueError('Deletion or replacement requires an explicit recovery decision; deployment stopped.')
        if change['type'] not in allowed_types:
            raise ValueError('Resource type is outside the permitted deployment contract.')
        after = change['change'].get('after') or {}
        if after.get('resource_group_name', expected) != expected:
            raise ValueError('Plan targets a resource group outside the own prefix.')
        name = after.get('name', '')
        identity = (change['type'], name)
        if name not in names[change['type']] or identity in seen:
            raise ValueError('Managed resource name/count is outside the exact course allowance.')
        seen.add(identity)
        if change['type'] == 'azurerm_container_app':
            template = after['template'][0]
            if template['min_replicas'] != 0 or template['max_replicas'] != 1:
                raise ValueError('Container replica limits differ from the course contract.')
        if change['type'] == 'azapi_resource':
            if after.get('type') != 'Microsoft.Sql/servers/databases@2023-08-01':
                raise ValueError('Unexpected AzAPI resource type.')
            body = after['body']
            if isinstance(body, str):
                body = json.loads(body)
            properties = body['properties']
            if (properties.get('useFreeLimit') is not True
                    or properties.get('freeLimitExhaustionBehavior') != 'AutoPause'
                    or 'maxSizeBytes' in properties or 'autoPauseDelay' in properties):
                raise ValueError('SQL must use the student free offer without paid overflow or fixed-limit overrides.')
    return True


if __name__ == '__main__':
    try:
        validate(json.load(sys.stdin), sys.argv[1])
        print('Plan accepted: own resources, no deletion/replacement, bounded replicas and free SQL.')
    except (KeyError, IndexError, TypeError, ValueError):
        print('Plan rejected: destructive, unknown or out-of-contract infrastructure change. Inspect privately before proceeding.', file=sys.stderr)
        sys.exit(1)
