"""
matching.services
------------------
Business logic lives here, separate from views, so the matching
algorithm can be unit-tested and reused (e.g. from a future admin
dashboard action or a management command) without going through HTTP.

This is the direct implementation of your stated requirement:
"The tutor matching system should prioritize tutors from the same
area before suggesting nearby areas."
"""

from apps.profiles.models import TutorProfile


def suggest_tutors_for_request(student_request, limit=10):
    """
    Returns a ranked list of TutorProfile candidates for a given
    StudentRequest, same-area tutors first.

    Ranking, in order:
      1. Tutor covers the request's exact area          (same_area=True)
      2. Tutor is verified and currently accepting students
      3. Tutor teaches at least one of the requested subjects
      4. Within each area tier, higher-rated tutors first

    Returns (results, same_area_ids) — same_area_ids lets the
    serializer flag which candidates matched on area, for display.
    """
    base_qs = (
        TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.VERIFIED,
            is_accepting_students=True,
            subjects__in=student_request.subjects.all(),
        )
        .distinct()
    )

    same_area_qs = base_qs.filter(preferred_areas=student_request.area).order_by("-rating_avg")
    same_area_ids = set(same_area_qs.values_list("id", flat=True))

    other_area_qs = base_qs.exclude(id__in=same_area_ids).order_by("-rating_avg")

    ranked = list(same_area_qs) + list(other_area_qs)
    return ranked[:limit], same_area_ids
