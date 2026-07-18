from django.urls import path

from .views import ParentLeadCreateView, StatusCheckView, TutorLeadCreateView

urlpatterns = [
    path("parent/", ParentLeadCreateView.as_view(), name="parent-lead"),
    path("tutor/", TutorLeadCreateView.as_view(), name="tutor-lead"),
    path("status/", StatusCheckView.as_view(), name="status-check"),
]
