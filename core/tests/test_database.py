"""F2 database: row level security everywhere, and the dbcheck command."""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connection
from django.test import SimpleTestCase, TestCase

from config.test_runner import drop_test_database
from core.rls import tables_without_rls


class RowLevelSecurityTests(TestCase):
    def test_every_public_table_has_row_level_security(self):
        # A hosted PostgreSQL (e.g. Supabase) may expose the public schema over HTTP.
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace AND relkind = 'r'")
            self.assertGreater(cursor.fetchone()[0], 10)
        self.assertEqual(tables_without_rls(connection), [])


class DbcheckCommandTests(TestCase):
    def run_dbcheck(self, *args):
        out = StringIO()
        call_command('dbcheck', *args, stdout=out)
        return out.getvalue()

    def test_passes_on_this_projects_database(self):
        output = self.run_dbcheck()
        self.assertIn('Connected: PostgreSQL', output)
        self.assertIn('Isolation: no tables from other projects.', output)
        self.assertIn('Row level security: on for every table.', output)
        self.assertIn('Database check passed.', output)

    def test_refuses_a_database_holding_another_projects_tables(self):
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE other_project_orders (id integer)')
        with self.assertRaisesMessage(CommandError, 'other_project_orders'):
            self.run_dbcheck()

    def test_reports_tables_without_row_level_security(self):
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE django_session DISABLE ROW LEVEL SECURITY')
        with self.assertRaisesMessage(CommandError, 'django_session'):
            self.run_dbcheck()
        self.assertIn('Database check passed.', self.run_dbcheck('--before-migrate'))


class FlakyCursor:
    """Fails the first `failures` statements, like a DROP that meets a busy autovacuum worker."""

    def __init__(self, failures):
        self.failures = failures
        self.statements = []

    def execute(self, sql):
        self.statements.append(sql)
        if len(self.statements) <= self.failures:
            raise DatabaseError('permission denied to terminate process')


class TestDatabaseDropTests(SimpleTestCase):
    def test_drop_is_retried_until_it_succeeds(self):
        cursor = FlakyCursor(failures=2)
        drop_test_database(cursor, '"test_app"', pause=0)
        self.assertEqual(cursor.statements, ['DROP DATABASE IF EXISTS "test_app" WITH (FORCE)'] * 3)

    def test_drop_gives_up_after_the_last_attempt(self):
        cursor = FlakyCursor(failures=10)
        with self.assertRaises(DatabaseError):
            drop_test_database(cursor, '"test_app"', attempts=3, pause=0)
        self.assertEqual(len(cursor.statements), 3)
