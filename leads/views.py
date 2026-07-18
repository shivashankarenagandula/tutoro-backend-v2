"""
leads.views
------------
The ONLY unauthenticated write endpoints in the whole API — these are
what the public marketing site actually calls. Explicitly throttled
here (not just relying on a global default) since this is the one
place an anonymous user can write to the database at all, making it
the most likely target for spam/abuse.
"""

from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import ParentLead, TutorLead
from .serializers import ParentLeadSerializer, TutorLeadSerializer


class LeadSubmitThrottle(AnonRateThrottle):
    scope = "lead_submit"


class ParentLeadCreateView(generics.CreateAPIView):
    serializer_class = ParentLeadSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LeadSubmitThrottle]


class TutorLeadCreateView(generics.CreateAPIView):
    serializer_class = TutorLeadSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LeadSubmitThrottle]


class StatusCheckThrottle(AnonRateThrottle):
    # Deliberately tighter than lead submission -- this endpoint's whole
    # job is looking up existing data by phone number, so it's the more
    # sensitive one to rate-limit against enumeration attempts.
    scope = "status_check"


STATUS_DISPLAY = {
    "NEW": "Received — we'll be in touch soon",
    "CONTACTED": "You've been contacted — we're working on your match",
    "CONVERTED": "Matched! Your tutor coordination is in progress",
    "CLOSED": "This request is closed",
}


class StatusCheckView(APIView):
    """
    Public status lookup, by exact name + phone match only (no partial
    matching, no listing) -- deliberately narrow so this can't be used
    to browse other people's data, only to confirm your own.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [StatusCheckThrottle]

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        phone = (request.data.get("phone_number") or "").strip().replace(" ", "").replace("-", "")

        if not name or not phone:
            return Response({"detail": "Name and phone number are required."}, status=400)

        parent_lead = (
            ParentLead.objects.filter(name__iexact=name, phone_number__endswith=phone[-10:])
            .order_by("-created_at")
            .first()
        )
        tutor_lead = (
            TutorLead.objects.filter(name__iexact=name, phone_number__endswith=phone[-10:])
            .order_by("-created_at")
            .first()
        )

        if not parent_lead and not tutor_lead:
            return Response(
                {"detail": "No request found with that name and phone number. Double-check your details, or WhatsApp us directly."},
                status=404,
            )

        results = []
        if parent_lead:
            results.append({
                "type": "parent",
                "area": parent_lead.area,
                "subject": parent_lead.subject,
                "status": parent_lead.status,
                "status_display": STATUS_DISPLAY.get(parent_lead.status, parent_lead.status),
                "submitted": parent_lead.created_at.strftime("%d %b %Y"),
            })
        if tutor_lead:
            results.append({
                "type": "tutor",
                "area": tutor_lead.area,
                "subjects": tutor_lead.subjects,
                "status": tutor_lead.status,
                "status_display": STATUS_DISPLAY.get(tutor_lead.status, tutor_lead.status),
                "submitted": tutor_lead.created_at.strftime("%d %b %Y"),
            })

        return Response({"results": results})
