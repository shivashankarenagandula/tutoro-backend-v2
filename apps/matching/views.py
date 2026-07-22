"""
matching.views
---------------
Three permission tiers in this one file, which is the whole point of
"Tutoro stays the coordinator":
  - Parents can create requests and see only their own
  - Nobody except staff can see the suggestion algorithm or create
    an Assignment — matching is explicitly staff-mediated, not
    something a tutor or parent can trigger themselves
  - Tutors never appear in this file at all — they interact via their
    own profile (apps.profiles) and, later, via Assignment/DemoClass
    read-only views (not needed yet at MVP volume; admin handles
    coordination directly over WhatsApp per your existing workflow)
"""

import math
import random
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole, IsParentRole
from apps.catalog.models import Area

from .models import Assignment, StudentRequest
from .serializers import AssignmentSerializer, StudentRequestSerializer, TutorSuggestionSerializer
from .services import suggest_tutors_for_request


class StudentRequestListCreateView(generics.ListCreateAPIView):
    """
    - Parent: sees and creates only their own requests
    - Admin: sees every request (needed to triage in the Stage 1
      internal tool), filterable by ?status= and ?area=
    """

    serializer_class = StudentRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = StudentRequest.objects.select_related("parent", "area").prefetch_related("subjects")

        if user.role == user.Role.ADMIN or user.is_staff:
            status_filter = self.request.query_params.get("status")
            area_filter = self.request.query_params.get("area")
            if status_filter:
                qs = qs.filter(status=status_filter)
            if area_filter:
                qs = qs.filter(area_id=area_filter)
            return qs.order_by("-created_at")

        # Non-admins only ever see their own — enforced here, not just
        # trusted to the client.
        return qs.filter(parent__user=user).order_by("-created_at")

    def get_permissions(self):
        if self.request.method == "POST":
            return [permissions.IsAuthenticated(), IsParentRole()]
        return [permissions.IsAuthenticated()]


class SuggestTutorsView(APIView):
    """
    GET /api/matching/requests/<id>/suggest-tutors/
    Admin-only. Returns ranked candidates, same-area first.
    """

    permission_classes = [IsAdminRole]

    def get(self, request, pk):
        student_request = get_object_or_404(StudentRequest, pk=pk)

        candidates, same_area_ids = suggest_tutors_for_request(student_request)
        serializer = TutorSuggestionSerializer(
            candidates, many=True, context={"same_area_ids": same_area_ids}
        )
        return Response({
            "student_request_id": str(student_request.id),
            "area": student_request.area.name,
            "count": len(candidates),
            "results": serializer.data,
        })


class AssignmentListCreateView(generics.ListCreateAPIView):
    """Admin-only — creating an Assignment IS the staff-mediated match."""

    serializer_class = AssignmentSerializer
    permission_classes = [IsAdminRole]
    queryset = Assignment.objects.select_related("student_request", "tutor", "matched_by").order_by("-created_at")


def _student_display_name(full_name):
    """
    Privacy: students shown on the public marketing site are (often)
    minors. Never expose a full name publicly — first name + last
    initial only, e.g. "Ananya Reddy" -> "Ananya R."
    """
    parts = full_name.strip().split()
    if not parts:
        return "A Student"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0]}."


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# Match statuses that represent a genuine, confirmed connection —
# not just a staff proposal that hasn't gone anywhere yet.
_LIVE_MATCH_STATUSES = [
    Assignment.Status.DEMO_SCHEDULED,
    Assignment.Status.DEMO_COMPLETED,
    Assignment.Status.ACCEPTED,
]


class RecentMatchByAreaView(APIView):
    """
    GET /api/matching/recent-match/?area=<area-slug>

    Public, read-only. Powers the "Live match, illustrated" card on
    the marketing site's per-location pages.

    Returns the most recent real match in that area if one exists;
    otherwise a clearly-flagged illustrative example (is_dummy=true)
    so the card never looks broken on a brand-new/low-volume area.

    Privacy: student name is reduced to first name + last initial
    (see _student_display_name). Tutor name is shown in full since
    tutors are adults who opted in as service providers. No contact
    details (phone/email/address) are ever included in this response.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        area_slug = request.query_params.get("area", "").strip()
        area = Area.objects.filter(slug__iexact=area_slug, is_active=True).first() if area_slug else None

        assignment = None
        if area:
            assignment = (
                Assignment.objects.select_related("student_request", "tutor", "student_request__area")
                .filter(student_request__area=area, status__in=_LIVE_MATCH_STATUSES)
                .order_by("-created_at")
                .first()
            )

        if assignment:
            tutor = assignment.tutor
            student_request = assignment.student_request

            distance_km = None
            tutor_area = tutor.preferred_areas.filter(
                latitude__isnull=False, longitude__isnull=False
            ).first()
            if area.latitude is not None and area.longitude is not None and tutor_area:
                distance_km = round(
                    _haversine_km(area.latitude, area.longitude, tutor_area.latitude, tutor_area.longitude), 1
                )

            return Response({
                "is_dummy": False,
                "student_display_name": _student_display_name(student_request.student_name),
                "student_class_display": student_request.get_student_class_display(),
                "subject": student_request.subjects.first().name if student_request.subjects.exists() else "",
                "area_name": area.name,
                "tutor_name": tutor.full_name,
                "tutor_qualification": tutor.qualification,
                "tutor_experience_years": tutor.experience_years,
                "distance_km": distance_km,
                "tutor_verified": tutor.verification_status == tutor.VerificationStatus.VERIFIED,
            })

        # No real match yet for this area (or no area/unknown slug) —
        # illustrative fallback so the card still renders sensibly.
        area_name = area.name if area else "your area"
        return Response({
            "is_dummy": True,
            "student_display_name": "Ananya",
            "student_class_display": "Class 8",
            "subject": "Maths",
            "area_name": area_name,
            "tutor_name": "Kiran",
            "tutor_qualification": "B.Tech",
            "tutor_experience_years": 4,
            "distance_km": round(random.uniform(1.5, 3.5), 1),
            "tutor_verified": True,
        })
