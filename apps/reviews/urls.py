from django.urls import path

from .views import (
    AdminReviewListView,
    ReviewCreateView,
    ReviewListView,
    ReviewPublishView,
)

urlpatterns = [
    path("", ReviewListView.as_view(), name="review-list"),
    path("submit/", ReviewCreateView.as_view(), name="review-submit"),
    path("admin/", AdminReviewListView.as_view(), name="review-admin-list"),
    path("<uuid:pk>/publish/", ReviewPublishView.as_view(), name="review-publish"),
]
