"""
accounts.views
---------------
Registration endpoints only — login/refresh use simplejwt's built-in
views directly (wired in config/urls.py), since our User model needs
no customization there: USERNAME_FIELD='email' is already all
simplejwt needs.

Both registration endpoints are public (AllowAny) by design — but
throttled via DEFAULT_THROTTLE_RATES (see settings) to stop signup-spam
abuse, since these are the only unauthenticated write endpoints in the
whole API.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ParentRegisterSerializer, TutorRegisterSerializer


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
