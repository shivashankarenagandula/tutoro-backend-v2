"""
matching.tests
----------------
Covers suggest_tutors_for_request()'s mode-branching logic (Phase 2
item 12 -- the original bug report was that this function ignored
teaching mode entirely and always did area-first ranking regardless).
These tests assert each branch actually returns the right pool.

use_ai_ranking=False everywhere here -- these tests check rule-based
filtering/ranking behavior, not the AI re-rank layer (apps.ai.client,
now backed by Gemini). Running without a real GEMINI_API_KEY should
never make these fail -- the AI layer degrades gracefully with no key
-- but skipping it here keeps these tests fast and deterministic
regardless of environment.
"""

from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Academy, Area, City, Subject
from apps.profiles.models import ParentProfile, TutorProfile

from .models import StudentRequest
from .services import suggest_tutors_for_request


class MatchingModeBranchingTests(TestCase):
    def setUp(self):
        city = City.objects.create(name="Hyderabad", state="Telangana", is_active=True)
        self.area = Area.objects.create(name="Kukatpally", slug="kukatpally", city=city, is_active=True)
        self.other_area = Area.objects.create(name="Miyapur", slug="miyapur", city=city, is_active=True)
        self.subject = Subject.objects.create(name="Maths", slug="maths")

        parent_user = User.objects.create_user(
            email="parent@test.com", phone_number="9111111101", password="testpass123",
            role=User.Role.PARENT,
        )
        self.parent = ParentProfile.objects.create(user=parent_user, full_name="Parent", area=self.area)

        self.home_tutor = self._make_tutor("home1@test.com", "9111111102", "HOME", self.area)
        self.online_tutor = self._make_tutor("online1@test.com", "9111111103", "ONLINE", self.area)
        self.both_tutor = self._make_tutor("both1@test.com", "9111111104", "BOTH", self.other_area)

        self.academy = Academy.objects.create(
            name="Bright Academy", is_active=True, classes_offered="C6_8,C9_10",
        )
        self.academy.areas_covered.add(self.area)
        self.academy.subjects.add(self.subject)

    def _make_tutor(self, email, phone, teaching_mode, area):
        user = User.objects.create_user(
            email=email, phone_number=phone, password="testpass123", role=User.Role.TUTOR,
        )
        tutor = TutorProfile.objects.create(
            user=user, full_name=f"Tutor {teaching_mode}", teaching_mode=teaching_mode,
            verification_status=TutorProfile.VerificationStatus.VERIFIED,
            is_accepting_students=True,
        )
        tutor.subjects.add(self.subject)
        tutor.preferred_areas.add(area)
        return tutor

    def _make_request(self, mode, student_class="C6_8", area=None):
        request = StudentRequest.objects.create(
            parent=self.parent, student_name="Kid", student_class=student_class,
            area=area or self.area, teaching_mode_preference=mode, consent_given=True,
        )
        request.subjects.add(self.subject)
        return request

    def test_home_mode_only_returns_home_and_both_tutors(self):
        request = self._make_request(StudentRequest.TeachingModePreference.HOME)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        result_ids = {t.id for t in results}
        self.assertIn(self.home_tutor.id, result_ids)
        self.assertIn(self.both_tutor.id, result_ids)
        self.assertNotIn(self.online_tutor.id, result_ids)
        self.assertEqual(mode, StudentRequest.TeachingModePreference.HOME)

    def test_home_mode_ranks_same_area_first(self):
        request = self._make_request(StudentRequest.TeachingModePreference.HOME)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        # home_tutor is in the request's own area; both_tutor is in a
        # different area -- same-area tutor should rank first.
        self.assertEqual(results[0].id, self.home_tutor.id)
        self.assertIn(self.home_tutor.id, same_area_ids)

    def test_online_mode_only_returns_online_and_both_tutors(self):
        request = self._make_request(StudentRequest.TeachingModePreference.ONLINE)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        result_ids = {t.id for t in results}
        self.assertIn(self.online_tutor.id, result_ids)
        self.assertIn(self.both_tutor.id, result_ids)
        self.assertNotIn(self.home_tutor.id, result_ids)
        self.assertEqual(mode, StudentRequest.TeachingModePreference.ONLINE)

    def test_online_mode_ignores_area_ranking(self):
        """The core Phase 2 rule: online candidates are never ranked by
        area, since distance is meaningless for a video call."""
        request = self._make_request(StudentRequest.TeachingModePreference.ONLINE)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        self.assertEqual(same_area_ids, set())

    def test_academy_mode_returns_no_tutors_only_academies(self):
        request = self._make_request(StudentRequest.TeachingModePreference.ACADEMY)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        self.assertIn(self.academy, results)
        self.assertNotIn(self.home_tutor, results)
        self.assertNotIn(self.online_tutor, results)
        self.assertEqual(mode, StudentRequest.TeachingModePreference.ACADEMY)

    def test_academy_not_returned_for_wrong_class_level(self):
        # academy only offers C6_8/C9_10 -- a C11_12 request shouldn't match
        request = self._make_request(StudentRequest.TeachingModePreference.ACADEMY, student_class="C11_12")
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        self.assertNotIn(self.academy, results)

    def test_any_mode_falls_back_through_pools_in_order(self):
        # Home tutors exist, so ANY should resolve to the HOME pool first.
        request = self._make_request(StudentRequest.TeachingModePreference.ANY)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        self.assertEqual(mode, StudentRequest.TeachingModePreference.HOME)
        self.assertTrue(len(results) > 0)

    def test_any_mode_falls_back_to_academy_when_no_tutors_at_all(self):
        # A subject no tutor teaches (only the academy does) empties both
        # the HOME and ONLINE pools -- ANY should fall all the way
        # through to ACADEMY.
        science = Subject.objects.create(name="Science", slug="science")
        self.academy.subjects.add(science)
        request = StudentRequest.objects.create(
            parent=self.parent, student_name="Kid", student_class="C6_8",
            area=self.area, teaching_mode_preference=StudentRequest.TeachingModePreference.ANY,
            consent_given=True,
        )
        request.subjects.add(science)
        results, same_area_ids, mode = suggest_tutors_for_request(request, use_ai_ranking=False)
        self.assertEqual(mode, StudentRequest.TeachingModePreference.ACADEMY)
        self.assertIn(self.academy, results)
