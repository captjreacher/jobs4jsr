import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from scripts import supabase_integration as harness


class HarnessTests(unittest.TestCase):
    def test_production_writes_require_explicit_approval(self):
        args=SimpleNamespace(write_fixtures=True,storage_fixtures=False)
        with self.assertRaises(ValueError): harness.approved(args,{})

    def test_storage_has_separate_guard(self):
        args=SimpleNamespace(write_fixtures=True,storage_fixtures=True)
        with self.assertRaises(ValueError):
            harness.approved(args,{'JOBS4JSR_INTEGRATION_WRITE_APPROVAL':'APPROVED_FIRST_RELEASE_SYNTHETIC_TESTS'})

    def test_generated_letter_upload_flag_must_remain_false(self):
        with self.assertRaises(ValueError):
            harness.approved(SimpleNamespace(write_fixtures=False,storage_fixtures=False),{'JOBS4JSR_LETTER_UPLOAD_APPROVED':'true'})

    def test_missing_identity_configuration_never_contacts_network(self):
        api=Mock()
        with self.assertRaises(ValueError):
            harness.run(SimpleNamespace(write_fixtures=False,storage_fixtures=False),{},api)
        api.call.assert_not_called()

    def test_permission_denial_does_not_hide_server_failure(self):
        api=harness.API('synthetic-key',Mock())
        api.session.request.return_value.status_code=403
        self.assertEqual(api.rows('jobs',None),[])
        api.session.request.return_value.status_code=500
        with self.assertRaises(AssertionError):api.rows('jobs',None)
