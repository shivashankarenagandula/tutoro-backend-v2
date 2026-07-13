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
from rest_framework.throttling import AnonRateThrottle

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
