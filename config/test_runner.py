from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class ProjectTestRunner(DiscoverRunner):
    """The test runner for this project.

    Interface language: tests run in English whatever language the site uses,
    so assertions on interface text hold for every site. A test about another
    language selects it itself with override_settings(LANGUAGE_CODE=...).

    Test database: dropped even when reached through a pooler. Supabase's
    session pooler (Supavisor) keeps a server connection open to the test
    database and reopens it immediately if terminated, so Django's plain DROP
    DATABASE fails with "being accessed by other users". Drop with FORCE
    (PostgreSQL 13+), which ends those sessions and drops atomically.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._interface_language = override_settings(LANGUAGE_CODE='en')
        self._interface_language.enable()

    def teardown_test_environment(self, **kwargs):
        self._interface_language.disable()
        super().teardown_test_environment(**kwargs)

    def teardown_databases(self, old_config, **kwargs):
        remaining = []
        for connection, old_name, destroy in old_config:
            if destroy and not self.keepdb and self.parallel <= 1 and connection.vendor == 'postgresql':
                test_name = connection.settings_dict['NAME']
                if self.verbosity >= 1:
                    print(f"Destroying test database for alias '{connection.alias}' ('{test_name}')...")
                connection.close()
                connection.settings_dict['NAME'] = old_name
                with connection._nodb_cursor() as cursor:
                    cursor.execute(f'DROP DATABASE IF EXISTS {connection.ops.quote_name(test_name)} WITH (FORCE)')
            else:
                remaining.append((connection, old_name, destroy))
        super().teardown_databases(remaining, **kwargs)
