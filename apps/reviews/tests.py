"""
reviews.tests
--------------
Zero coverage previously existed for this app, despite Review carrying
the anti-fraud property the models.py docstring calls out explicitly:
a review can only be left by the parent who actually owns the
Assignment it's tied to. These tests exist to pin that property down,
plus the publish/visibility rules around it -- if any of these ever
regress, either a fake review becomes postable, or a real one leaks
publicly before staff have moderated it.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.catalog.models import Area, City, Subject
from apps.matching.models import Assignment, StudentRequest
from apps.profiles.models import ParentProfile, TutorProfile

from .models import Review


def _auth_client(user):
    client = APIClient()
    token = RefreshToken.for_user(user).access_token
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


class ReviewFixtureMixin:
    _phone_counter = 9000000000

    def _next_phone(self):
        # Every fixture user needs a distinct phone_number -- it's a
        # unique field on User -- so this hands out a fresh one per call
        # instead of hardcoding a value that collides the second time
        # any of these helpers run in the same test.
        ReviewFixtureMixin._phone_counter += 1
        return str(ReviewFixtureMixin._phone_counter)

    def _make_parent(self, email, area):
        user = User.objects.create_user(
            email=email, phone_number=self._next_phone(), password="testpass123", role=User.Role.PARENT
        )
        profile = ParentProfile.objects.create(user=user, full_name="Test Parent", area=area)
        return user, profile

    def _make_tutor(self, email):
        user = User.objects.create_user(
            email=email, phone_number=self._next_phone(), password="testpass123", role=User.Role.TUTOR
        )
        profile = TutorProfile.objects.create(user=user, full_name="Test Tutor")
        return user, profile

    def _make_assignment(self, parent_profile, tutor_profile, area, subject, status):
        request = StudentRequest.objects.create(
            parent=parent_profile,
            student_name="Student One",
            student_class="C6_8",
            area=area,
            status=StudentRequest.Status.MATCHED,
        )
        request.subjects.add(subject)
        return Assignment.objects.create(
            student_request=request, tutor=tutor_profile, status=status
        )

    def setUp(self):
        self.city = City.objects.create(name="Hyderabad", state="Telangana", is_active=True)
        self.area = Area.objects.create(name="Kukatpally", city=self.city, is_active=True)
        self.subject = Subject.objects.create(name="Maths", slug="maths")

        self.parent_user, self.parent_profile = self._make_parent("parent@example.com", self.area)
        self.tutor_user, self.tutor_profile = self._make_tutor("tutor@example.com")

        self.other_parent_user, self.other_parent_profile = self._make_parent(
            "otherparent@example.com", self.area
        )


class ReviewSubmissionTests(ReviewFixtureMixin, TestCase):
    def test_parent_can_review_own_ended_assignment(self):
        assignment = self._make_assignment(
            self.parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.ENDED,
        )
        client = _auth_client(self.parent_user)
        response = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 5, "comment": "Great tutor!"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        review = Review.objects.get(assignment=assignment)
        self.assertEqual(review.reviewer_id, self.parent_user.id)
        self.assertEqual(review.tutor_id, self.tutor_profile.id)
        # Never auto-published, regardless of AI moderation outcome.
        self.assertFalse(review.is_published)

    def test_parent_cannot_review_someone_elses_assignment(self):
        """The anti-fraud property from the model docstring: this is
        what stops a parent leaving a review on a match they had
        nothing to do with."""
        assignment = self._make_assignment(
            self.other_parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.ENDED,
        )
        client = _auth_client(self.parent_user)
        response = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 5, "comment": "Not my match"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_cannot_review_assignment_still_proposed(self):
        assignment = self._make_assignment(
            self.parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.PROPOSED,
        )
        client = _auth_client(self.parent_user)
        response = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 4, "comment": "Too early"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_cannot_review_same_assignment_twice(self):
        assignment = self._make_assignment(
            self.parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.ACCEPTED,
        )
        client = _auth_client(self.parent_user)
        first = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 5, "comment": "First review"},
            format="json",
        )
        self.assertEqual(first.status_code, 201)

        second = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 1, "comment": "Trying again"},
            format="json",
        )
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Review.objects.filter(assignment=assignment).count(), 1)

    def test_tutor_cannot_submit_a_review(self):
        """Only parents submit reviews -- IsParentRole should block a
        tutor from posting here even with a valid assignment."""
        assignment = self._make_assignment(
            self.parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.ENDED,
        )
        client = _auth_client(self.tutor_user)
        response = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 5, "comment": "Self-review attempt"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_anonymous_cannot_submit_a_review(self):
        assignment = self._make_assignment(
            self.parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.ENDED,
        )
        client = APIClient()
        response = client.post(
            "/api/reviews/submit/",
            {"assignment": str(assignment.id), "rating": 5, "comment": "No auth"},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))


class ReviewVisibilityTests(ReviewFixtureMixin, TestCase):
    def _make_review(self, is_published):
        assignment = self._make_assignment(
            self.parent_profile, self.tutor_profile, self.area, self.subject,
            status=Assignment.Status.ENDED,
        )
        return Review.objects.create(
            assignment=assignment, reviewer=self.parent_user, tutor=self.tutor_profile,
            rating=5, comment="Nice", is_published=is_published,
        )

    def test_public_listing_only_returns_published_reviews(self):
        published = self._make_review(is_published=True)
        self._make_review(is_published=False)

        response = APIClient().get("/api/reviews/")
        ids = [r["id"] for r in response.json()["results"]]

        self.assertIn(str(published.id), ids)
        self.assertEqual(len(ids), 1)

    def test_admin_queue_includes_unpublished_reviews(self):
        self._make_review(is_published=False)
        admin_user = User.objects.create_user(
            email="admin@example.com", phone_number=self._next_phone(), password="testpass123",
            role=User.Role.ADMIN,
        )
        admin_user.is_staff = True
        admin_user.save(update_fields=["is_staff"])

        client = _auth_client(admin_user)
        response = client.get("/api/reviews/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)

    def test_non_admin_cannot_access_moderation_queue(self):
        client = _auth_client(self.parent_user)
        response = client.get("/api/reviews/admin/")
        self.assertEqual(response.status_code, 403)

    def test_publishing_updates_tutor_rating_average(self):
        review = self._make_review(is_published=False)
        admin_user = User.objects.create_user(
            email="admin2@example.com", phone_number=self._next_phone(), password="testpass123",
            role=User.Role.ADMIN,
        )
        admin_user.is_staff = True
        admin_user.save(update_fields=["is_staff"])

        self.tutor_profile.refresh_from_db()
        self.assertEqual(self.tutor_profile.total_reviews, 0)

        client = _auth_client(admin_user)
        response = client.patch(
            f"/api/reviews/{review.id}/publish/", {"is_published": True}, format="json"
        )
        self.assertEqual(response.status_code, 200)

        self.tutor_profile.refresh_from_db()
        self.assertEqual(self.tutor_profile.total_reviews, 1)
        self.assertEqual(self.tutor_profile.rating_avg, 5)
      
