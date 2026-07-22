from django.urls import path

from .views import (
    AssignmentListCreateView,
    RecentMatchByAreaView,
    StudentRequestListCreateView,
    SuggestTutorsView,
)

urlpatterns = [
    path("requests/", StudentRequestListCreateView.as_view(), name="student-requests"),
    path("requests/<uuid:pk>/suggest-tutors/", SuggestTutorsView.as_view(), name="suggest-tutors"),
    path("assignments/", AssignmentListCreateView.as_view(), name="assignments"),
    path("recent-match/", RecentMatchByAreaView.as_view(), name="recent-match"),
]
