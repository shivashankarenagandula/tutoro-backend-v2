from django.urls import path

from .views import (
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterParentView,
    RegisterTutorView,
    RequestOTPView,
    VerifyOTPView,
)

urlpatterns = [
    path("register/parent/", RegisterParentView.as_view(), name="register-parent"),
    path("register/tutor/", RegisterTutorView.as_view(), name="register-tutor"),
    path("otp/request/", RequestOTPView.as_view(), name="otp-request"),
    path("otp/verify/", VerifyOTPView.as_view(), name="otp-verify"),
    path("password-reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
