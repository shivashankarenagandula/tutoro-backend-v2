"""
profiles.models
----------------
Role-specific data that sits on top of accounts.User.

Kept separate from User itself so the auth table stays lean, and so
adding tutor-only or parent-only fields later never touches the
authentication model (lower risk of breaking login while iterating on
profile features).
"""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.accounts.models import User
from apps.catalog.models import Area, Subject


def tutor_document_path(instance, filename):
    return f"tutors/{instance.user_id}/documents/{filename}"


def tutor_photo_path(instance, filename):
    return f"tutors/{instance.user_id}/photo/{filename}"


class ParentProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="parent_profile")

    full_name = models.CharField(max_length=150)
    alternate_phone = models.CharField(max_length=15, blank=True)

    address_line = models.CharField(max_length=255, blank=True)
    area = models.ForeignKey(Area, on_delete=models.SET_NULL, null=True, related_name="parents")
    pincode = models.CharField(max_length=10, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles_parent"

    def __str__(self):
        return self.full_name


class TutorProfile(models.Model):
    class TeachingMode(models.TextChoices):
        ONLINE = "ONLINE", "Online only"
        OFFLINE = "OFFLINE", "Home visit only"
        BOTH = "BOTH", "Both"

    class FeeType(models.TextChoices):
        PER_HOUR = "PER_HOUR", "Per hour"
        PER_MONTH = "PER_MONTH", "Per month"

    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="tutor_profile")

    full_name = models.CharField(max_length=150)
    bio = models.TextField(blank=True)
    qualification = models.CharField(max_length=200, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)

    profile_photo = models.ImageField(upload_to=tutor_photo_path, null=True, blank=True)
    resume_file = models.FileField(upload_to=tutor_document_path, null=True, blank=True)
    qualification_document = models.FileField(
        upload_to=tutor_document_path, null=True, blank=True
    )

    subjects = models.ManyToManyField(Subject, related_name="tutors", blank=True)
    preferred_areas = models.ManyToManyField(Area, related_name="tutors", blank=True)

    teaching_mode = models.CharField(
        max_length=10, choices=TeachingMode.choices, default=TeachingMode.OFFLINE
    )
    fee_type = models.CharField(max_length=10, choices=FeeType.choices, default=FeeType.PER_HOUR)
    expected_fee = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    verification_status = models.CharField(
        max_length=10, choices=VerificationStatus.choices, default=VerificationStatus.PENDING
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="tutors_verified"
    )

    # Whether the tutor is currently open to new student matches.
    # Lets a tutor "pause" without deleting their profile/history.
    is_accepting_students = models.BooleanField(default=True)

    # Denormalized fields, updated via a signal whenever a Review is saved.
    # Kept here (instead of computing on every request) because tutor
    # listing/sorting by rating happens often and shouldn't require an
    # aggregate query every time.
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    total_reviews = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "profiles_tutor"
        indexes = [
            models.Index(fields=["verification_status", "is_accepting_students"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.verification_status})"


class TutorAvailability(models.Model):
    """
    Recurring weekly availability slots, e.g. "Monday 6-8 PM".
    Separate table (not a JSON blob on TutorProfile) so we can later
    query "which tutors are free Tuesday evening" directly in SQL.
    """

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tutor = models.ForeignKey(
        TutorProfile, on_delete=models.CASCADE, related_name="availability_slots"
    )
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        db_table = "profiles_tutor_availability"
        unique_together = [("tutor", "weekday", "start_time", "end_time")]

    def __str__(self):
        return f"{self.tutor.full_name} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"
