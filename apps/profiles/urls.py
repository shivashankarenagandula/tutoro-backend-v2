from django.urls import path

from .views import (
    GenerateTutorBioView,
    MyParentProfileView,
    MyTutorProfileView,
    TutorSearchView,
    VerifyTutorView,
)

urlpatterns = [
    path("parents/me/", MyParentProfileView.as_view(), name="my-parent-profile"),
    path("tutors/me/", MyTutorProfileView.as_view(), name="my-tutor-profile"),
    path("tutors/me/generate-bio/", GenerateTutorBioView.as_view(), name="generate-tutor-bio"),
    path("tutors/search/", TutorSearchView.as_view(), name="tutor-search"),
    path("tutors/<uuid:pk>/verify/", VerifyTutorView.as_view(), name="verify-tutor"),
]
