"""
reviews.models
---------------
Reviews are tied to a specific Assignment (not just "a tutor got 5
stars from someone") — this means a review can only be left by a
parent who actually had a real, staff-coordinated match with that
tutor. That's an important anti-fraud property: it stops fake reviews
from people with no real Assignment history.
"""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.accounts.models import User
from apps.matching.models import Assignment
from apps.profiles.models import TutorProfile


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    assignment = models.OneToOneField(
        Assignment,
        on_delete=models.CASCADE,
        related_name="review",
        help_text="One review per assignment — ties every review to a real, staff-verified match.",
    )
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_written")
    tutor = models.ForeignKey(TutorProfile, on_delete=models.CASCADE, related_name="reviews")

    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)

    # Moderation flag — don't show unmoderated reviews publicly by default.
    is_published = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews_review"
        indexes = [models.Index(fields=["tutor", "is_published"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.rating}\u2605 for {self.tutor.full_name}"


# ---------------------------------------------------------------------
# SIGNAL: keep TutorProfile.rating_avg / total_reviews in sync.
# Lives here (not in profiles app) to avoid a circular import, since
# profiles doesn't need to know reviews exist, only the reverse.
# ---------------------------------------------------------------------
from django.db.models import Avg, Count
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver


@receiver([post_save, post_delete], sender=Review)
def update_tutor_rating(sender, instance, **kwargs):
    stats = Review.objects.filter(tutor=instance.tutor, is_published=True).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    TutorProfile.objects.filter(pk=instance.tutor_id).update(
        rating_avg=stats["avg"] or 0, total_reviews=stats["count"] or 0
    )
