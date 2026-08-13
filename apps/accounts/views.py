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
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import EmailOTP, PasswordResetOTP, User
from .serializers import (
    ParentRegisterSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    TutorRegisterSerializer,
)


class LoginThrottle(AnonRateThrottle):
    """
    Keyed by IP (AnonRateThrottle's default), not by the email being
    attempted -- this stops one attacker from brute-forcing a single
    account without limit by only throttling per-target, and also
    means one attacker can't exhaust another legitimate user's login
    attempts by submitting under their email.
    """
    scope = "login"


class TutoroTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Stock simplejwt only puts token_type/exp/iat/jti/user_id in the
    access token -- no email, role, full_name, or is_verified. The
    frontend auth modal decodes the token client-side to greet the
    user and show their role without an extra round trip, so those
    claims need to actually be in there or every field it reads comes
    back empty right after login (full_name/role were only ever
    populated right after signup, where the frontend had them from the
    form directly -- a real bug this fixes).
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["is_verified"] = user.is_verified

        full_name = ""
        if user.role == User.Role.PARENT and hasattr(user, "parent_profile"):
            full_name = user.parent_profile.full_name
        elif user.role == User.Role.TUTOR and hasattr(user, "tutor_profile"):
            full_name = user.tutor_profile.full_name
        token["full_name"] = full_name

        return token


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """
    Drop-in replacement for simplejwt's TokenObtainPairView with login
    throttling applied. Wire this into urls.py in place of the
    original -- request/response behavior is otherwise identical.
    """
    throttle_classes = [LoginThrottle]
    serializer_class = TutoroTokenObtainPairSerializer


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


# ---------------------------------------------------------------------
# Password reset ("forgot password") -- both endpoints below are
# unauthenticated by design (AllowAny): a user who forgot their
# password can't log in to prove who they are, so identity is instead
# proven by possession of the code sent to their inbox.
# ---------------------------------------------------------------------


class PasswordResetRequestThrottle(AnonRateThrottle):
    """
    Keyed by IP, same reasoning as LoginThrottle: this endpoint sends a
    real email and (unlike login) has no account to key throttling on
    since the caller may not even have an account.
    """
    scope = "password_reset_request"


class PasswordResetConfirmThrottle(AnonRateThrottle):
    scope = "password_reset_confirm"


def _send_password_reset_email(user, code):
    if not settings.EMAIL_HOST_USER:
        raise RuntimeError("Email is not configured on the server.")
    send_mail(
        subject="Reset your Tutoro password",
        message=(
            f"Your Tutoro password reset code is {code}.\n\n"
            f"It expires in {PasswordResetOTP.VALIDITY_MINUTES} minutes. "
            f"If you didn't request this, you can safely ignore this email -- "
            f"your password won't be changed."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


class PasswordResetRequestView(APIView):
    """
    POST /api/auth/password-reset/request/  body: {"email": "..."}

    Always returns the same generic 200 message whether or not the
    email belongs to a real account -- returning different responses
    for "sent" vs "no such account" is a classic account-enumeration
    leak, so the client can never tell the difference.
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    GENERIC_MESSAGE = "If an account exists for that email, a password reset code has been sent."

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email).first()
        if user:
            otp = PasswordResetOTP.generate_for(user)
            try:
                _send_password_reset_email(user, otp.code)
            except Exception:
                # Fail silently to the client for the same enumeration
                # reason as above -- an SMTP outage shouldn't reveal
                # "yes, that account exists, but we couldn't email it".
                pass

        return Response({"message": self.GENERIC_MESSAGE})


class PasswordResetConfirmView(APIView):
    """
    POST /api/auth/password-reset/confirm/
    body: {"email": "...", "code": "123456", "new_password": "..."}
    """

    permission_classes = [permissions.AllowAny]
    throttle_classes = [PasswordResetConfirmThrottle]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.filter(email__iexact=data["email"]).first()
        # Same code/message regardless of which part is wrong (no such
        # user vs wrong code vs expired code) -- again, don't let the
        # response shape confirm whether the email is registered.
        invalid_response = Response(
            {"detail": "That code is invalid or has expired."}, status=400
        )
        if not user:
            return invalid_response

        otp = (
            PasswordResetOTP.objects.filter(user=user, code=data["code"], is_used=False)
            .order_by("-created_at")
            .first()
        )
        if not otp or not otp.is_valid():
            return invalid_response

        otp.is_used = True
        otp.save(update_fields=["is_used"])

        user.set_password(data["new_password"])
        user.save(update_fields=["password"])

        return Response({"message": "Password reset successfully. You can now log in."})
