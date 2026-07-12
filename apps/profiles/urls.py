from django.urls import path

from .views import MyParentProfileView, MyTutorProfileView, VerifyTutorView

urlpatterns = [
    path("parents/me/", MyParentProfileView.as_view(), name="my-parent-profile"),
    path("tutors/me/", MyTutorProfileView.as_view(), name="my-tutor-profile"),
    path("tutors/<uuid:pk>/verify/", VerifyTutorView.as_view(), name="verify-tutor"),
]
