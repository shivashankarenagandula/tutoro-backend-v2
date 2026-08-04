"""
matching.models
-----------------
The core of the business: a parent's request for a tutor, and the
match (Assignment) between that request and a specific tutor.

DESIGN DECISION — Tutoro stays the coordinator:
`Assignment.matched_by` records which admin/staff user made the match.
`Assignment` and `DemoClass` are the audit trail proving Tutoro
arranged and stayed involved in the connection — this matters both
operationally (you asked for this explicitly) and for any future
commission/subscription billing, since you need a record of which
matches Tutoro facilitated.
"""

import uuid

from django.db import models

from apps.accounts.models import User
from apps.catalog.models import Academy, Area, StudentClass, Subject
from apps.profiles.models import ParentProfile, TutorProfile


class StudentRequest(models.Model):
    """
    One request = one child needing a tutor for one or more subjects.
    A parent with two kids needing tutoring submits two StudentRequests.
    """

    # StudentClass moved to apps.catalog (shared with Academy.classes_offered
    # so both sides of an AcademyReferral speak the same values) -- kept
    # importable here as StudentRequest.StudentClass so existing callers
    # (e.g. `StudentRequest.StudentClass.C1_5`) don't break.
    StudentClass = StudentClass

    class Board(models.TextChoices):
        CBSE = "CBSE", "CBSE"
        ICSE = "ICSE", "ICSE"
        STATE = "STATE", "State Board"
        IB = "IB", "IB"
        OTHER = "OTHER", "Other"

    class TeachingModePreference(models.TextChoices):
        ONLINE = "ONLINE", "Online"
        HOME = "HOME", "Home visit"
        ACADEMY = "ACADEMY", "Academy / coaching institute"
        ANY = "ANY", "Any of the above"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open — awaiting match"
        MATCHED = "MATCHED", "Tutor proposed"
        DEMO_SCHEDULED = "DEMO_SCHEDULED", "Demo scheduled"
        CONVERTED = "CONVERTED", "Converted to ongoing classes"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled by parent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey(
        ParentProfile, on_delete=models.CASCADE, related_name="student_requests"
    )

    student_name = models.CharField(max_length=150)
    student_class = models.CharField(max_length=15, choices=StudentClass.choices)
    board = models.CharField(max_length=10, choices=Board.choices, default=Board.STATE)

    subjects = models.ManyToManyField(Subject, related_name="student_requests")
    area = models.ForeignKey(Area, on_delete=models.PROTECT, related_name="student_requests")

    teaching_mode_preference = models.CharField(
        max_length=10,
        choices=TeachingModePreference.choices,
        default=TeachingModePreference.HOME,
    )
    preferred_timing = models.CharField(max_length=150, blank=True)

    budget_min = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    notes = models.TextField(blank=True)

    # DPDP consent -- captured at submission time, not backfilled later.
    # consent_version lets you tell which wording of the privacy notice
    # someone actually agreed to if the policy text changes down the line.
    consent_given = models.BooleanField(
        default=False,
        help_text="Parent consented to Tutoro processing this data per the DPDP Act.",
    )
    consent_given_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(
        max_length=20, blank=True,
        help_text="Which version of the privacy notice was shown when consent was given.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matching_student_request"
        indexes = [
            models.Index(fields=["status", "area"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_name} ({self.get_student_class_display()}) - {self.area}"


class Assignment(models.Model):
    """
    A proposed or confirmed match between a StudentRequest and a
    TutorProfile. One StudentRequest can have several Assignment rows
    over time (e.g. first tutor didn't work out) — never overwrite,
    always create a new row, so history is never lost.
    """

    class Status(models.TextChoices):
        PROPOSED = "PROPOSED", "Proposed — awaiting demo"
        DEMO_SCHEDULED = "DEMO_SCHEDULED", "Demo scheduled"
        DEMO_COMPLETED = "DEMO_COMPLETED", "Demo completed"
        ACCEPTED = "ACCEPTED", "Ongoing classes"
        DECLINED = "DECLINED", "Declined after demo"
        ENDED = "ENDED", "Classes ended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_request = models.ForeignKey(
        StudentRequest, on_delete=models.CASCADE, related_name="assignments"
    )
    tutor = models.ForeignKey(TutorProfile, on_delete=models.CASCADE, related_name="assignments")

    # Who on the Tutoro team made this match — required, since matching
    # is explicitly staff-mediated, not a self-serve marketplace action.
    matched_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="assignments_made"
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROPOSED)

    # Set when the assignment is ONLINE (or BOTH and this particular
    # match is running online) -- a recurring meeting link (Google Meet/
    # Zoom) used across the ongoing classes for this match, distinct from
    # DemoClass.video_class_link which is per individual demo session.
    video_class_link = models.URLField(blank=True)

    started_at = models.DateTimeField(null=True, blank=True, help_text="When ongoing classes began.")
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matching_assignment"
        unique_together = [("student_request", "tutor")]
        indexes = [models.Index(fields=["status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_request.student_name} <-> {self.tutor.full_name} ({self.status})"


class DemoClass(models.Model):
    """
    A specific demo class attempt tied to an Assignment. Split out from
    Assignment because a single assignment can have a reschedule/no-show
    before a demo actually happens — you want that history queryable,
    not overwritten.
    """

    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        COMPLETED = "COMPLETED", "Completed"
        NO_SHOW = "NO_SHOW", "No-show"
        CANCELLED = "CANCELLED", "Cancelled"
        RESCHEDULED = "RESCHEDULED", "Rescheduled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="demo_classes")

    scheduled_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.SCHEDULED)

    # Per-session link, since a demo might reschedule onto a different
    # call than the recurring one later used for ongoing classes
    # (Assignment.video_class_link).
    video_class_link = models.URLField(blank=True)

    feedback_from_parent = models.TextField(blank=True)
    feedback_from_tutor = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "matching_demo_class"
        ordering = ["-scheduled_at"]

    def __str__(self):
        return f"Demo for {self.assignment} on {self.scheduled_at:%d %b %Y}"


class AcademyReferral(models.Model):
    """
    The ACADEMY-mode counterpart to Assignment: links a StudentRequest to
    an Academy instead of a TutorProfile. Kept as a separate model (not
    a nullable academy FK bolted onto Assignment) because the two have
    genuinely different lifecycles -- Assignment tracks demo classes and
    ongoing tutor billing; a referral's job ends once the academy
    confirms enrollment, so its status flow is intentionally simpler.
    """

    class Status(models.TextChoices):
        REFERRED = "REFERRED", "Referred to academy"
        CONTACTED = "CONTACTED", "Academy contacted the family"
        ENROLLED = "ENROLLED", "Enrolled"
        DECLINED = "DECLINED", "Declined / not proceeding"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student_request = models.ForeignKey(
        StudentRequest, on_delete=models.CASCADE, related_name="academy_referrals"
    )
    academy = models.ForeignKey(
        Academy, on_delete=models.CASCADE, related_name="referrals"
    )

    # Same staff-mediation pattern as Assignment.matched_by -- Tutoro
    # stays the record-of-truth for who made the referral.
    referred_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="academy_referrals_made"
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REFERRED)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "matching_academy_referral"
        unique_together = [("student_request", "academy")]
        indexes = [models.Index(fields=["status"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student_request.student_name} -> {self.academy.name} ({self.status})"
