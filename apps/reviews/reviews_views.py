"""
reviews.views
--------------
Three tiers, mirroring the pattern already used in apps.matching.views:

  ReviewListView       -- public, published reviews only (tutor
                           listing pages read from this).
  ReviewCreateView      -- parent-only, write their own review for an
                           assignment they actually had.
  AdminReviewListView /
  ReviewPublishView     -- staff-only moderation queue + the actual
                           publish/unpublish action.
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole, IsParentRole

from .models import Review
from .serializers import ReviewCreateSerializer, ReviewSerializer
from .services import moderate_review


class ReviewListView(generics.ListAPIView):
    """
    GET /api/reviews/?tutor=<tutor_id>
    Public. Only ever returns published reviews -- unpublished rows
    are only visible via AdminReviewListView.
    """

    serializer_class = ReviewSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Review.objects.filter(is_published=True).select_related(
            "tutor", "reviewer__parent_profile"
        )
        tutor_id = self.request.query_params.get("tutor")
        if tutor_id:
            qs = qs.filter(tutor_id=tutor_id)
        return qs


class ReviewCreateView(generics.CreateAPIView):
    """POST /api/reviews/submit/ -- parent submits a review for one of
    their own completed/ongoing assignments. Starts unpublished."""

    serializer_class = ReviewCreateSerializer
    permission_classes = [permissions.IsAuthenticated, IsParentRole]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = serializer.save()
        # Synchronous, best-effort -- there's no task queue in this
        # project (see apps.leads.signals for the same reasoning), and
        # a single short JSON-mode call is fast enough to run inline
        # here without meaningfully delaying the response. Never raises
        # (see reviews.services.moderate_review docstring), so it can't
        # turn a successful review submission into a failed request.
        moderate_review(review)
        review.refresh_from_db()
        return Response(
            ReviewSerializer(review).data,
            status=201,
        )


class AdminReviewListView(generics.ListAPIView):
    """
    GET /api/reviews/admin/?is_published=false
    Staff-only moderation queue. Defaults to showing unpublished
    reviews first (what staff actually need to act on) but supports
    filtering either way.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = Review.objects.select_related("tutor", "reviewer__parent_profile").order_by(
            "is_published", "-created_at"
        )
        is_published = self.request.query_params.get("is_published")
        if is_published is not None:
            qs = qs.filter(is_published=is_published.lower() in ("1", "true", "yes"))
        moderation_status = self.request.query_params.get("ai_moderation_status")
        if moderation_status:
            qs = qs.filter(ai_moderation_status=moderation_status.upper())
        return qs


class ReviewPublishView(APIView):
    """
    PATCH /api/reviews/<id>/publish/  body: {"is_published": true|false}
    Staff-only. Separate from a general update endpoint deliberately --
    publishing is a moderation decision, not "editing a review",
    so it doesn't accidentally let staff rewrite rating/comment too.
    """

    permission_classes = [IsAdminRole]

    def patch(self, request, pk):
        review = get_object_or_404(Review, pk=pk)

        is_published = request.data.get("is_published")
        if is_published is None:
            return Response({"detail": "is_published is required."}, status=400)

        review.is_published = bool(is_published)
        review.save(update_fields=["is_published"])
        return Response(ReviewSerializer(review).data)
