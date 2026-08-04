from django.urls import path

from .views import RegisterParentView, RegisterTutorView, RequestOTPView, VerifyOTPView

urlpatterns = [
    path("register/parent/", RegisterParentView.as_view(), name="register-parent"),
    path("register/tutor/", RegisterTutorView.as_view(), name="register-tutor"),
    path("otp/request/", RequestOTPView.as_view(), name="otp-request"),
    path("otp/verify/", VerifyOTPView.as_view(), name="otp-verify"),
]
