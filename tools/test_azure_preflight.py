"""Policy intersections and refusal boundaries without Azure access."""
import unittest
from unittest.mock import patch
from azure_preflight import region_lists, run


class PreflightTests(unittest.TestCase):
    def test_intersects_flat_and_arm_policy_envelopes(self):
        policies = [{'displayName': 'Allowed resource deployment regions', 'parameters': {
            'listOfAllowedLocations': {'value': ['West Europe', 'North Europe']}}},
            {'properties': {'displayName': 'Allowed locations', 'parameters': {
                'allowedLocations': {'value': ['westeurope', 'spaincentral']}}}}]
        self.assertEqual(region_lists(policies), ['westeurope'])
        self.assertEqual(region_lists([]), [])

    @patch('azure_preflight.read', return_value=[])
    def test_no_login_stops_before_other_calls(self, read):
        with self.assertRaisesRegex(RuntimeError, 'No signed-in'):
            run()
        self.assertEqual(read.call_count, 1)

    @patch('azure_preflight.read')
    def test_disabled_subscription_is_refused(self, read):
        identifier = '00000000-0000-0000-0000-000000000001'
        read.return_value = [{'id': identifier, 'name': 'Renamed subscription', 'state': 'Disabled', 'tenantId': 'tenant'}]
        with self.assertRaisesRegex(RuntimeError, 'not present and Enabled'):
            run(identifier)
        self.assertEqual(read.call_count, 1)

    @patch('azure_preflight.read')
    def test_name_alone_does_not_select_subscription(self, read):
        read.return_value = [{'id': 'id', 'name': 'IE subscription', 'state': 'Enabled', 'tenantId': 'tenant'}]
        self.assertIn('next_step', run())
        self.assertEqual(read.call_count, 1)


if __name__ == '__main__':
    unittest.main()
