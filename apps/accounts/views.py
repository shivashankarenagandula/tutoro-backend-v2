"""
accounts.views
---------------
Registration endpoints, plus a throttled login view.

Login previously used simplejwt's TokenObtainPairView directly (wired
in config/urls.py) since our User model needs no field customization
there -- USERNAME_FIELD='email' is already all simplejwt needs. But
that meant login had NO throttle at all: the one endpoint where an
attacker gets direct pass/fail feedback on password guesses. This
subclass adds the 'login' throttle scope (see DEFAULT_THROTTLE_RATES
in settings) while keeping simplejwt's actual auth logic untouched.

Both registration endpoints are public (AllowAny) by design — but
throttled via DEFAULT_THROTTLE_RATES (see settings) to stop signup-spam
abuse, since these are the only unauthenticated write endpoints in the
whole API.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import ParentRegisterSerializer, TutorRegisterSerializer


class LoginThrottle(AnonRateThrottle):
    """
    Keyed by IP (AnonRateThrottle's default), not by the email being
    attempted -- this stops one attacker from brute-forcing a single
    account without limit by only throttling per-target, and also
    means one attacker can't exhaust another legitimate user's login
    attempts by submitting under their email.
    """
    scope = "login"


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """
    Drop-in replacement for simplejwt's TokenObtainPairView with login
    throttling applied. Wire this into urls.py in place of the
    original -- request/response behavior is otherwise identical.
    """
    throttle_classes = [LoginThrottle]


class RegisterParentView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ParentRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(
            {
                "message": "Parent account created.",
                "parent_id": str(profile.id),
                "email": profile.user.email,
            },
            status=status.HTTP_201_CREATED,
        )


class RegisterTutorView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = TutorRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(
            {
                "message": "Tutor account created. Verification is pending review.",
                "tutor_id": str(profile.id),
                "email": profile.user.email,
                "verification_status": profile.verification_status,
            },
            status=status.HTTP_201_CREATED,
        )
