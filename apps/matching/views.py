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

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole, IsParentRole

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
