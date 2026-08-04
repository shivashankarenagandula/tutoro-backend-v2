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

Also: RequestOTPView / VerifyOTPView, which make User.is_verified
actually functional (see EmailOTP in models.py).
"""

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import EmailOTP
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


class OTPRequestThrottle(UserRateThrottle):
    """Keyed by user (not IP) -- a logged-in user requesting too many
    codes for their own account is what this guards against, not
    shared-IP false positives."""
    scope = "otp_request"


class OTPVerifyThrottle(UserRateThrottle):
    """
    Separate, slightly looser scope from otp_request -- someone
    fat-fingering their code a couple of times shouldn't burn through
    the same budget as requesting a fresh email, but repeated wrong
    guesses still needs a ceiling since a 6-digit code is only ~1M
    possibilities.
    """
    scope = "otp_verify"


def _send_otp_email(user, code):
    if not settings.EMAIL_HOST_USER:
        raise RuntimeError("Email is not configured on the server.")
    send_mail(
        subject="Your Tutoro verification code",
        message=(
            f"Your Tutoro verification code is {code}.\n\n"
            f"It expires in {EmailOTP.VALIDITY_MINUTES} minutes. "
            f"If you didn't request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


class RequestOTPView(APIView):
    """
    POST /api/auth/otp/request/
    Authenticated. Generates and emails a fresh 6-digit code, replacing
    any earlier unused one for this user (see EmailOTP.generate_for).
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [OTPRequestThrottle]

    def post(self, request):
        if request.user.is_verified:
            return Response({"detail": "Your account is already verified."}, status=400)

        otp = EmailOTP.generate_for(request.user)
        try:
            _send_otp_email(request.user, otp.code)
        except Exception:
            # The OTP row is already created -- fine to leave it; the
            # user can just request again once email is working. Never
            # leak SMTP internals to the client.
            return Response(
                {"detail": "Couldn't send the verification email right now. Please try again shortly."},
                status=503,
            )
        return Response({"message": f"Verification code sent to {request.user.email}."})


class VerifyOTPView(APIView):
    """
    POST /api/auth/otp/verify/  body: {"code": "123456"}
    Authenticated. On success, flips User.is_verified to True -- the
    one place in the codebase that field actually gets set outside of
    create_superuser.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):
        code = str(request.data.get("code", "")).strip()
        if not code:
            return Response({"detail": "code is required."}, status=400)

        otp = (
            EmailOTP.objects.filter(user=request.user, code=code, is_used=False)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid():
            return Response({"detail": "That code is invalid or has expired."}, status=400)

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        request.user.is_verified = True
        request.user.save(update_fields=["is_verified"])

        return Response({"message": "Email verified.", "is_verified": True})
