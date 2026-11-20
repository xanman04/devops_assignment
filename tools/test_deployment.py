"""Deployment safety and bounded health checks without Azure or credentials."""
import copy
import json
import unittest
from unittest.mock import patch
from deployment_guard import validate
from azure_bootstrap import names, role, validate_storage
from deploy_azure import health


def app_plan():
    return {'resource_changes': [{'type': 'azurerm_container_app', 'mode': 'managed', 'change': {
        'actions': ['update'], 'after': {'name': 'student-discovery', 'resource_group_name': 'rg-student',
            'template': [{'min_replicas': 0, 'max_replicas': 1}]}}}]}


class GuardTests(unittest.TestCase):
    @patch('azure_bootstrap.az')
    def test_scoped_role_lookup_never_combines_all_and_scope(self, azure):
        azure.return_value = [{'principalId': 'principal', 'scope': '/own/group', 'roleDefinitionName': 'Contributor'}]
        role('principal', '/own/group', 'Contributor')
        azure.assert_called_once_with('role', 'assignment', 'list', '--scope', '/own/group')

    def test_existing_storage_must_be_owned_private_and_on_correct_tier(self):
        account = {'tags': {'owner': 'student'}, 'allowBlobPublicAccess': False,
                   'allowSharedKeyAccess': False, 'kind': 'StorageV2', 'sku': {'name': 'Standard_LRS'}}
        validate_storage(account, 'student')
        for key, value in [('allowBlobPublicAccess', True), ('allowSharedKeyAccess', True), ('tags', {}), ('sku', {'name': 'Premium_LRS'})]:
            altered = {**account, key: value}
            with self.assertRaises(RuntimeError): validate_storage(altered, 'student')

    def test_third_app_duplicate_or_extra_database_is_refused(self):
        for name in ('student-third-app', 'student-other-db'):
            plan = app_plan(); plan['resource_changes'][0]['change']['after']['name'] = name
            with self.assertRaises(ValueError): validate(plan, 'student')
        plan = app_plan(); plan['resource_changes'].append(copy.deepcopy(plan['resource_changes'][0]))
        with self.assertRaises(ValueError): validate(plan, 'student')
    def test_valid_own_app_and_ie_names(self):
        self.assertTrue(validate(app_plan(), 'student'))
        self.assertEqual(names('xc.ieu2023'), ('xc-ieu2023', 'rg-xc-ieu2023', 'xcieu2023ui'))
        for student in ('../other', 'UPPERCASE', 'person@example.com'):
            with self.assertRaises(ValueError): names(student)

    def test_delete_replacement_other_group_vm_and_replica_drift_are_refused(self):
        for field, value in [('actions', ['delete']), ('actions', ['delete', 'create'])]:
            plan = app_plan(); plan['resource_changes'][0]['change'][field] = value
            with self.assertRaises(ValueError): validate(plan, 'student')
        for key, value in [('name', 'other-app'), ('resource_group_name', 'rg-another-student')]:
            plan = app_plan(); plan['resource_changes'][0]['change']['after'][key] = value
            with self.assertRaises(ValueError): validate(plan, 'student')
        plan = app_plan(); plan['resource_changes'][0]['type'] = 'azurerm_linux_virtual_machine'
        with self.assertRaises(ValueError): validate(plan, 'student')
        plan = app_plan(); plan['resource_changes'][0]['change']['after']['template'][0]['min_replicas'] = 1
        with self.assertRaises(ValueError): validate(plan, 'student')

    def test_paid_overflow_or_free_offer_overrides_are_refused(self):
        props = {'useFreeLimit': True, 'freeLimitExhaustionBehavior': 'AutoPause'}
        plan = {'resource_changes': [{'type': 'azapi_resource', 'change': {'actions': ['create'],
            'after': {'name': 'student-discovery-db', 'type': 'Microsoft.Sql/servers/databases@2023-08-01', 'body': {'properties': props}}}}]}
        self.assertTrue(validate(plan, 'student'))
        third = copy.deepcopy(plan)
        third['resource_changes'][0]['change']['after']['name'] = 'student-third-db'
        with self.assertRaises(ValueError): validate(third, 'student')
        for key, value in [('useFreeLimit', False), ('freeLimitExhaustionBehavior', 'BillOverUsage'), ('maxSizeBytes', 2), ('autoPauseDelay', 15)]:
            altered = copy.deepcopy(plan); altered['resource_changes'][0]['change']['after']['body']['properties'][key] = value
            with self.assertRaises(ValueError): validate(altered, 'student')


class Response:
    def __init__(self, version, db='ok'):
        self.payload = json.dumps({'db': db, 'version': version}).encode(); self.offset = 0
        self.status = 200
    def read(self, *_): return self.payload
    def __enter__(self): return self
    def __exit__(self, *_): pass


class HealthTests(unittest.TestCase):
    @patch('deploy_azure.time.sleep')
    @patch('deploy_azure.urlopen')
    def test_stale_revision_retries_until_exact_sha(self, open_url, sleep):
        open_url.side_effect = [Response('old'), Response('tested')]
        health({'discovery': 'https://service.example'}, 'tested')
        self.assertEqual(open_url.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    @patch('deploy_azure.time.monotonic', side_effect=[0, 481])
    def test_deadline_fails_without_unbounded_wait(self, clock):
        with self.assertRaisesRegex(RuntimeError, 'deadline exceeded'):
            health({'groups': 'https://service.example'}, 'tested')


if __name__ == '__main__': unittest.main()
