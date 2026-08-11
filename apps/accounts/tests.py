"""
accounts.tests
----------------
Not really about accounts specifically -- this lives here because it's
a project-wide sanity check and every app already depends on accounts,
so it's guaranteed to run whenever the test suite runs at all.

test_no_missing_migrations is the regression test for a real incident:
apps.leads.models had consent_given/consent_given_at/consent_version
fields with NO migration ever generated for them, which meant any real
deploy would fail (Postgres has no matching columns) while `python
manage.py check` stayed silent about it -- check doesn't inspect
migration state at all. This test calls the same machinery
`makemigrations --check --dry-run` uses, so this exact class of bug
fails the test suite instead of surfacing as a production crash.
"""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class MigrationConsistencyTests(TestCase):
    def test_no_missing_migrations(self):
        """
        Fails if any app's models.py has changes that don't have a
        corresponding migration file yet. This is exactly the check
        that would have caught apps.leads' missing consent-field
        migration before it ever reached a real deploy.
        """
        output = StringIO()
        try:
            call_command(
                "makemigrations", "--check", "--dry-run", stdout=output, stderr=output,
            )
        except SystemExit as exc:
            # makemigrations --check exits with a non-zero code (via
            # SystemExit) when changes are missing a migration -- this
            # is the actual failure signal, not a normal command exit.
            self.fail(
                "Model changes exist with no matching migration. "
                "Run `python manage.py makemigrations` and commit the "
                f"result.\n\nDetails:\n{output.getvalue()}"
            ) if exc.code != 0 else None
