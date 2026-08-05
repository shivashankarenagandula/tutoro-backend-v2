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
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole
from apps.audit.models import AuditLog
from apps.ai.client import AIUnavailableError, complete, complete_json

from .models import ParentProfile, TutorProfile
from .serializers import ParentProfileSerializer, TutorProfileSerializer


class GenerateBioThrottle(UserRateThrottle):
    """Bio generation uses the higher-quality (pricier) Sonnet model,
    not Haiku -- a tighter per-user cap than most AI endpoints here."""
    scope = "generate_bio"


class GenerateTutorBioView(APIView):
    """
    POST /api/profiles/tutors/me/generate-bio/
    Phase 4 item 19. Drafts a bio from the tutor's own existing profile
    fields (qualification, experience, subjects, teaching mode) and
    returns it as suggested text -- it does NOT save it to the profile.
    The tutor reviews/edits the draft, then saves it themselves via the
    normal PATCH /api/profiles/tutors/me/ like any other bio edit. This
    keeps a human in the loop on their own public-facing profile text
    rather than an AI silently overwriting what they wrote, and reuses
    the existing profile-update endpoint instead of adding a second
    write path for the same field.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [GenerateBioThrottle]

    def post(self, request):
        tutor = get_object_or_404(TutorProfile, user=request.user)

        subjects = ", ".join(tutor.subjects.values_list("name", flat=True)) or "not specified"
        mode_label = tutor.get_teaching_mode_display()

        system = (
            "You write short, warm, professional third-person bios for tutors on "
            "an Indian home-tuition and online-tutoring marketplace called Tutoro. "
            "Write 2-3 sentences, 60-90 words. No markdown, no headers, no emoji, "
            "no made-up specifics (schools, awards, numbers) beyond what's given. "
            "Respond with ONLY the bio text -- no preamble, no quotation marks."
        )
        user_prompt = (
            f"Tutor name: {tutor.full_name}\n"
            f"Qualification: {tutor.qualification or 'not specified'}\n"
            f"Years of experience: {tutor.experience_years}\n"
            f"Subjects taught: {subjects}\n"
            f"Teaching mode: {mode_label}"
        )

        try:
            draft_bio = complete(system, user_prompt, model="claude-sonnet-5", max_tokens=200)
        except AIUnavailableError:
            return Response(
                {"detail": "Bio generation isn't available right now. Please write your bio manually."},
                status=503,
            )
        except Exception:
            return Response(
                {"detail": "Couldn't generate a bio right now. Please try again shortly."},
                status=503,
            )

        return Response({"suggested_bio": draft_bio.strip()})


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


class TutorSearchThrottle(UserRateThrottle):
    scope = "tutor_search"

    def get_cache_key(self, request, view):
        # Public endpoint -- IsAuthenticated isn't required, so fall
        # back to IP-based throttling for anonymous callers the way
        # AnonRateThrottle would, since UserRateThrottle alone returns
        # None (i.e. no throttling at all) for an unauthenticated user.
        if request.user and request.user.is_authenticated:
            return super().get_cache_key(request, view)
        ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class TutorSearchView(generics.ListAPIView):
    """
    GET /api/profiles/tutors/search/?area=<id>&subject=<id>&q=<free text>
    Phase 4 item 22. Public. `area`/`subject` are hard filters (exact
    match, same as the rest of the platform); `q` is optional and, when
    present, triggers an AI re-rank of the filtered results by how well
    each tutor's bio matches the free-text query -- same pattern and
    same fallback behavior as ai_rerank_by_notes in apps.matching.services
    (falls back to rating-sorted order on any AI failure, never breaks
    search itself).

    There was no public tutor-listing endpoint at all before this --
    only "my own profile" (MyTutorProfileView) and an internal,
    request-specific suggestion list (apps.matching). This is the
    first endpoint a parent could actually browse tutors from directly,
    which the roadmap's "semantic search on tutor listings" implicitly
    assumes exists.
    """

    serializer_class = TutorProfileSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [TutorSearchThrottle]

    def get_queryset(self):
        qs = TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.VERIFIED,
            is_accepting_students=True,
        ).distinct()

        area_id = self.request.query_params.get("area")
        if area_id:
            qs = qs.filter(preferred_areas__id=area_id)

        subject_id = self.request.query_params.get("subject")
        if subject_id:
            qs = qs.filter(subjects__id=subject_id)

        return qs.order_by("-rating_avg")[:30]

    def list(self, request, *args, **kwargs):
        queryset = list(self.get_queryset())
        query_text = request.query_params.get("q", "").strip()

        if query_text and len(queryset) > 1:
            queryset = self._ai_rerank(query_text, queryset)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def _ai_rerank(self, query_text, tutors):
        import json

        tutor_summaries = [
            {"id": str(t.id), "bio": (t.bio or "")[:500], "qualification": t.qualification}
            for t in tutors
        ]
        system = (
            "You rank tutors on a tutoring marketplace by how well each tutor's "
            "bio and qualification match a parent's free-text search query. "
            "Respond with ONLY a JSON array of tutor id strings, best match "
            "first, including every id given exactly once. No prose, no fences."
        )
        try:
            ranked_ids = complete_json(
                system, json.dumps({"query": query_text, "tutors": tutor_summaries}), max_tokens=500
            )
        except Exception:  # noqa: broad -- AI re-rank is an enhancement, search must still work
            return tutors

        if not isinstance(ranked_ids, list):
            return tutors
        by_id = {str(t.id): t for t in tutors}
        reranked = [by_id[tid] for tid in ranked_ids if tid in by_id]
        return reranked if len(reranked) == len(tutors) else tutors


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
