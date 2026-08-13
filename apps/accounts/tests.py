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
from rest_framework.test import APIClient

from apps.catalog.models import Area, City
from apps.profiles.models import TutorProfile


class TutorSignupExpectedFeeTests(TestCase):
    """
    Regression test: the tutor signup form on the marketing site only
    has one generic "Expected fee" input (name="expected_fee"), but
    TutorRegisterSerializer used to only accept the split online_fee/
    home_visit_fee fields -- so `expected_fee` was an unrecognized key
    on a plain Serializer and got silently dropped. Every tutor who
    signed up lost the fee they typed in, with no error shown anywhere.
    Fixed by accepting `expected_fee` and backfilling both fee fields
    with it when they aren't given explicitly (see
    TutorRegisterSerializer.create in serializers.py).
    """

    def setUp(self):
        self.client = APIClient()
        city = City.objects.create(name="Hyderabad", state="Telangana", is_active=True)
        self.area = Area.objects.create(name="Kukatpally", city=city, is_active=True)

    def test_expected_fee_from_signup_form_is_saved(self):
        payload = {
            "email": "newtutor@example.com",
            "phone_number": "9123456780",
            "password": "testpass123",
            "full_name": "New Tutor",
            "subjects": ["Maths", "Physics"],
            "preferred_areas": [str(self.area.id)],
            "experience_years": 3,
            "expected_fee": "600",
        }
        response = self.client.post("/api/auth/register/tutor/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)

        profile = TutorProfile.objects.get(user__email="newtutor@example.com")
        self.assertEqual(profile.online_fee, 600)
        self.assertEqual(profile.home_visit_fee, 600)

    def test_explicit_online_and_home_fees_are_not_overridden(self):
        """If a caller ever does send the split fields directly (e.g. a
        future richer signup form), expected_fee should never clobber
        an explicitly-given value."""
        payload = {
            "email": "newtutor2@example.com",
            "phone_number": "9123456781",
            "password": "testpass123",
            "full_name": "New Tutor Two",
            "subjects": ["Maths"],
            "preferred_areas": [str(self.area.id)],
            "expected_fee": "600",
            "online_fee": "400",
            "home_visit_fee": "800",
        }
        response = self.client.post("/api/auth/register/tutor/", payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)

        profile = TutorProfile.objects.get(user__email="newtutor2@example.com")
        self.assertEqual(profile.online_fee, 400)
        self.assertEqual(profile.home_visit_fee, 800)


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
