"""
catalog.tests
--------------
This app had zero test coverage despite being the one thing every
other public form on the marketing site depends on directly: the
area/subject dropdowns are populated straight from these endpoints,
and apps.leads.serializers._validate_area_name re-checks against the
same is_active flag at submission time. If is_active filtering ever
regresses here, both the dropdown AND the form's own validation break
together, silently.
"""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Area, City, Subject


class CatalogPublicAccessTests(TestCase):
    """Nothing in this app requires auth -- these are the same endpoints
    an anonymous visitor's browser calls on every page load."""

    def setUp(self):
        self.client = APIClient()

    def test_areas_endpoint_is_public(self):
        response = self.client.get("/api/catalog/areas/")
        self.assertEqual(response.status_code, 200)

    def test_cities_endpoint_is_public(self):
        response = self.client.get("/api/catalog/cities/")
        self.assertEqual(response.status_code, 200)

    def test_subjects_endpoint_is_public(self):
        response = self.client.get("/api/catalog/subjects/")
        self.assertEqual(response.status_code, 200)


class ActiveFilteringTests(TestCase):
    """
    This is the property the whole "admin disables an area from the
    dashboard, zero redeploy" promise in views.py depends on. If this
    regresses, the frontend's area dropdown -- and therefore what
    parents/tutors can actually submit -- silently drifts from what
    admin thinks is turned on.
    """

    def setUp(self):
        self.client = APIClient()
        self.city = City.objects.create(name="Hyderabad", state="Telangana", is_active=True)

    def test_inactive_area_excluded_from_listing(self):
        Area.objects.create(name="Active Area", city=self.city, is_active=True)
        Area.objects.create(name="Paused Area", city=self.city, is_active=False)

        response = self.client.get("/api/catalog/areas/")
        names = [a["name"] for a in response.json()["results"]]

        self.assertIn("Active Area", names)
        self.assertNotIn("Paused Area", names)

    def test_area_excluded_when_its_city_is_inactive(self):
        """
        An area can be individually is_active=True but still shouldn't
        surface publicly if its parent city has been paused -- views.py
        filters on city__is_active=True precisely for this case.
        """
        paused_city = City.objects.create(name="Paused City", state="Telangana", is_active=False)
        Area.objects.create(name="Orphaned Area", city=paused_city, is_active=True)

        response = self.client.get("/api/catalog/areas/")
        names = [a["name"] for a in response.json()["results"]]

        self.assertNotIn("Orphaned Area", names)

    def test_inactive_subject_excluded_from_listing(self):
        Subject.objects.create(name="Active Subject", slug="active-subject", is_active=True)
        Subject.objects.create(name="Retired Subject", slug="retired-subject", is_active=False)

        response = self.client.get("/api/catalog/subjects/")
        names = [s["name"] for s in response.json()["results"]]

        self.assertIn("Active Subject", names)
        self.assertNotIn("Retired Subject", names)

    def test_inactive_city_excluded_from_listing(self):
        City.objects.create(name="Paused City 2", state="Telangana", is_active=False)

        response = self.client.get("/api/catalog/cities/")
        names = [c["name"] for c in response.json()["results"]]

        self.assertNotIn("Paused City 2", names)
