"""Opt-in runner for disposable local SQL Server databases provisioned by CI.

Never creates/drops databases and never connects to Azure. This mode flushes
the configured local database. Enable only in disposable integration stacks.
"""
from django.core.management import call_command
from django.test.runner import DiscoverRunner


class LocalSqlServerRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        call_command("migrate", interactive=False, verbosity=0)
        call_command("flush", interactive=False, verbosity=0)
        return []

    def teardown_databases(self, old_config, **kwargs):
        pass
