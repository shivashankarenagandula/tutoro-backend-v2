from django.urls import path

from .views import ParentLeadCreateView, TutorLeadCreateView

urlpatterns = [
    path("parent/", ParentLeadCreateView.as_view(), name="parent-lead"),
    path("tutor/", TutorLeadCreateView.as_view(), name="tutor-lead"),
]
