from django.urls import path

from .views import AssignmentListCreateView, StudentRequestListCreateView, SuggestTutorsView

urlpatterns = [
    path("requests/", StudentRequestListCreateView.as_view(), name="student-requests"),
    path("requests/<uuid:pk>/suggest-tutors/", SuggestTutorsView.as_view(), name="suggest-tutors"),
    path("assignments/", AssignmentListCreateView.as_view(), name="assignments"),
]
