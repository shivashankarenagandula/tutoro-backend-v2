"""
leads.models
-------------
DESIGN NOTE: these are deliberately NOT the same as StudentRequest /
TutorProfile in apps.matching / apps.profiles. Those require a full
User account (email + password) — appropriate once someone is
actually being onboarded. But the marketing site's forms are simple
lead capture (name, phone, area) with no password field, and adding
one just to request a free demo would hurt conversion for no reason.

So: this app is the public front door. A ParentLead/TutorLead is raw,
unauthenticated form input. Staff review it in Django admin and, when
ready to actually onboard someone, manually create the real User +
Profile (or extend this later with a "convert to account" admin
action) — matching the staff-mediated coordination model this whole
platform is built around.
"""

import uuid

from django.db import models


class LeadStatus(models.TextChoices):
    NEW = "NEW", "New"
    CONTACTED = "CONTACTED", "Contacted"
    CONVERTED = "CONVERTED", "Converted to account"
    CLOSED = "CLOSED", "Closed / not proceeding"


class ParentLead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    area = models.CharField(max_length=100, help_text="Validated against active Area names at submission time.")

    student_class = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    preferred_timing = models.CharField(max_length=150, blank=True)

    status = models.CharField(max_length=10, choices=LeadStatus.choices, default=LeadStatus.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leads_parent_lead"
        indexes = [models.Index(fields=["status", "area"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.area}) - {self.status}"


class TutorLead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    area = models.CharField(max_length=100, help_text="Validated against active Area names at submission time.")

    subjects = models.CharField(max_length=255, blank=True)
    classes = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=100, blank=True)
    expected_fee = models.CharField(max_length=100, blank=True)

    status = models.CharField(max_length=10, choices=LeadStatus.choices, default=LeadStatus.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leads_tutor_lead"
        indexes = [models.Index(fields=["status", "area"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.area}) - {self.status}"
