import time

from django.db import DatabaseError
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

DROP_ATTEMPTS = 5


class ProjectTestRunner(DiscoverRunner):
    """The test runner for this project.

    Interface language: tests run in English whatever language the site uses,
    so assertions on interface text hold for every site. A test about another
    language selects it itself with override_settings(LANGUAGE_CODE=...).

    Test database: dropped even when reached through a pooler. Supabase's
    session pooler (Supavisor) keeps a server connection open to the test
    database and reopens it immediately if terminated, so Django's plain DROP
    DATABASE fails with "being accessed by other users". Drop with FORCE
    (PostgreSQL 13+), which ends those sessions and drops atomically. FORCE
    fails with "permission denied to terminate process" while a server process
    the role may not end (autovacuum, for a role that is not a superuser, as on
    Supabase) is working in the database, so the drop is retried for a few seconds.
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
                    drop_test_database(cursor, connection.ops.quote_name(test_name))
            else:
                remaining.append((connection, old_name, destroy))
        super().teardown_databases(remaining, **kwargs)


def drop_test_database(cursor, quoted_name, attempts=DROP_ATTEMPTS, pause=1.0):
    for attempt in range(1, attempts + 1):
        try:
            cursor.execute(f'DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)')
            return
        except DatabaseError:
            if attempt == attempts:
                raise
            time.sleep(pause)
