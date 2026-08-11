"""
leads.tests
------------
Covers the two things about this app that have already broken once in
practice (per real conversation history with the person maintaining
this project):
  1. Model fields existing with no matching migration (see
     test_no_missing_migrations in apps.accounts.tests -- that's the
     project-wide version of this check).
  2. The frontend and backend disagreeing about what a valid lead
     submission looks like (missing consent_given broke the live site
     forms once already) -- test_lead_requires_consent below is
     specifically the regression test for that.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from apps.catalog.models import Area, City

from .models import ParentLead, TutorLead


class LeadSubmissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        city = City.objects.create(name="Hyderabad", state="Telangana", is_active=True)
        self.area = Area.objects.create(name="Kukatpally", city=city, is_active=True)

        self.valid_parent_payload = {
            "name": "Test Parent",
            "phone_number": "9876543210",
            "student_class": "Class 6-8",
            "subject": "Maths",
            "area": "Kukatpally",
            "preferred_timing": "Evening",
            "teaching_mode_preference": "ONLINE",
            "email": "",
            "consent_given": True,
        }
        self.valid_tutor_payload = {
            "name": "Test Tutor",
            "phone_number": "9876543211",
            "area": "Kukatpally",
            "subjects": "Maths, Physics",
            "classes": "6-10",
            "experience": "3 years",
            "expected_fee": "600/hr",
            "email": "",
            "consent_given": True,
        }

    def test_parent_lead_succeeds_with_consent(self):
        response = self.client.post("/api/leads/parent/", self.valid_parent_payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ParentLead.objects.count(), 1)
        lead = ParentLead.objects.first()
        self.assertTrue(lead.consent_given)
        self.assertIsNotNone(lead.consent_given_at)

    def test_parent_lead_rejected_without_consent(self):
        """
        Regression test: this exact scenario (consent_given missing/False)
        is what broke live form submissions in production once already,
        because the frontend didn't send the field the backend required.
        """
        payload = {**self.valid_parent_payload, "consent_given": False}
        response = self.client.post("/api/leads/parent/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent_given", response.json())
        self.assertEqual(ParentLead.objects.count(), 0)

    def test_parent_lead_rejected_for_unsupported_area(self):
        payload = {**self.valid_parent_payload, "area": "Somewhere Not Covered"}
        response = self.client.post("/api/leads/parent/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("area", response.json())

    def test_tutor_lead_succeeds_with_consent(self):
        response = self.client.post("/api/leads/tutor/", self.valid_tutor_payload, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(TutorLead.objects.count(), 1)

    def test_tutor_lead_rejected_without_consent(self):
        payload = {**self.valid_tutor_payload, "consent_given": False}
        response = self.client.post("/api/leads/tutor/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(TutorLead.objects.count(), 0)


class DuplicateLeadDetectionTests(TestCase):
    """Covers apps.leads.signals.flag_duplicate_parent_lead -- rule-based
    duplicate flagging by matching phone number within the lookback
    window."""

    def setUp(self):
        city = City.objects.create(name="Hyderabad", state="Telangana", is_active=True)
        Area.objects.create(name="Kukatpally", city=city, is_active=True)

    def test_second_lead_same_phone_flagged_as_duplicate(self):
        first = ParentLead.objects.create(
            name="Parent One", phone_number="9999999999", area="Kukatpally",
            student_class="C6_8", consent_given=True,
        )
        second = ParentLead.objects.create(
            name="Parent One Again", phone_number="9999999999", area="Kukatpally",
            student_class="C6_8", consent_given=True,
        )
        second.refresh_from_db()
        self.assertTrue(second.is_potential_duplicate)
        self.assertEqual(second.duplicate_of_id, first.id)

    def test_different_phone_not_flagged(self):
        ParentLead.objects.create(
            name="Parent One", phone_number="9999999999", area="Kukatpally",
            student_class="C6_8", consent_given=True,
        )
        second = ParentLead.objects.create(
            name="Parent Two", phone_number="8888888888", area="Kukatpally",
            student_class="C6_8", consent_given=True,
        )
        second.refresh_from_db()
        self.assertFalse(second.is_potential_duplicate)
