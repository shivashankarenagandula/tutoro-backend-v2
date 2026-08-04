"""
reviews.serializers
---------------------
Two shapes for two audiences, same model:

  ReviewSerializer        -- public-facing read shape (tutor listing
                              pages, admin list view). Never accepts
                              writes.
  ReviewCreateSerializer   -- parent-facing write shape. Only exposes
                              `assignment`, `rating`, `comment` -- every
                              other field (`reviewer`, `tutor`,
                              `is_published`) is derived server-side so
                              a parent can never review on someone
                              else's behalf, review a tutor they were
                              never actually matched with, or publish
                              their own review.
"""

from rest_framework import serializers

from apps.matching.models import Assignment

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    """Read-only. Used for both the public listing and admin moderation
    queue -- the admin view just also includes unpublished rows via the
    queryset, not a different serializer shape."""

    tutor_name = serializers.CharField(source="tutor.full_name", read_only=True)
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "assignment", "tutor", "tutor_name", "reviewer_name",
            "rating", "comment", "is_published",
            "ai_moderation_status", "ai_moderation_notes", "created_at",
        ]
        read_only_fields = fields

    def get_reviewer_name(self, obj):
        # Parents are the reviewers today (see ReviewCreateSerializer);
        # this stays generic so a future tutor-reviews-parent direction
        # doesn't need a serializer rewrite, just a real name to show.
        parent_profile = getattr(obj.reviewer, "parent_profile", None)
        return parent_profile.full_name if parent_profile else obj.reviewer.email


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "assignment", "rating", "comment"]
        read_only_fields = ["id"]

    def validate_assignment(self, assignment):
        request = self.context["request"]

        # Anti-fraud property from the model docstring, enforced here:
        # a review can only be left by the parent who actually owns the
        # StudentRequest this Assignment belongs to.
        parent_profile = getattr(request.user, "parent_profile", None)
        if not parent_profile or assignment.student_request.parent_id != parent_profile.id:
            raise serializers.ValidationError(
                "You can only review a tutor you were actually matched with."
            )

        # Reviewing only makes sense once classes genuinely happened --
        # not while still PROPOSED/DEMO_SCHEDULED, and not for a match
        # that was DECLINED before ever starting.
        reviewable_statuses = {Assignment.Status.ACCEPTED, Assignment.Status.ENDED}
        if assignment.status not in reviewable_statuses:
            raise serializers.ValidationError(
                "This assignment hasn't reached ongoing/ended classes yet, "
                "so it can't be reviewed."
            )

        # The DB's OneToOneField already enforces one review per
        # assignment, but that surfaces as an opaque IntegrityError --
        # catching it here gives a real validation message instead.
        if Review.objects.filter(assignment=assignment).exists():
            raise serializers.ValidationError("This assignment already has a review.")

        return assignment

    def create(self, validated_data):
        assignment = validated_data["assignment"]
        validated_data["reviewer"] = self.context["request"].user
        validated_data["tutor"] = assignment.tutor
        # Never publish on creation -- see AI review moderation
        # (Phase 4 roadmap item 20) and ReviewPublishView below.
        validated_data["is_published"] = False
        return super().create(validated_data)
