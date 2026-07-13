"""
profiles.views
---------------
Profiles use a "my profile" pattern (GET/PATCH on a fixed URL, no id
in the path) rather than a full ModelViewSet, because there is exactly
one profile per user — asking the client to know its own profile's
UUID just to fetch it is unnecessary friction. Admins get a separate,
explicit verification endpoint instead, since that's a distinct
business action (not a generic field edit) and deserves its own
audit-logged code path.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole
from apps.audit.models import AuditLog

from .models import ParentProfile, TutorProfile
from .serializers import ParentProfileSerializer, TutorProfileSerializer


class MyParentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ParentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(ParentProfile, user=self.request.user)


class MyTutorProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = TutorProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_404(TutorProfile, user=self.request.user)


class VerifyTutorView(APIView):
    """
    Admin-only. POST {"status": "VERIFIED" | "REJECTED"} to
    /api/profiles/tutors/<id>/verify/

    Writes an AuditLog row — this is the safety-critical action in the
    whole platform (a tutor being cleared to be matched with a child),
    so "who verified this tutor and when" must never be silently lost.
    """

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        tutor = get_object_or_404(TutorProfile, pk=pk)
        new_status = request.data.get("status")

        if new_status not in (TutorProfile.VerificationStatus.VERIFIED, TutorProfile.VerificationStatus.REJECTED):
            return Response(
                {"detail": "status must be VERIFIED or REJECTED."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = tutor.verification_status
        tutor.verification_status = new_status
        tutor.verified_at = timezone.now()
        tutor.verified_by = request.user
        tutor.save(update_fields=["verification_status", "verified_at", "verified_by"])

        AuditLog.objects.create(
            actor=request.user,
            action=AuditLog.Action.VERIFY if new_status == TutorProfile.VerificationStatus.VERIFIED else AuditLog.Action.REJECT,
            target_model="TutorProfile",
            target_id=str(tutor.id),
            metadata={"old_status": old_status, "new_status": new_status},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return Response({"tutor_id": str(tutor.id), "verification_status": tutor.verification_status})
