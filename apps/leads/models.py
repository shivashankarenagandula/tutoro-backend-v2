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

# Bump this string whenever the privacy notice shown alongside the
# consent checkbox changes materially -- consent_version on each lead
# records which wording someone actually agreed to, per DPDP Act
# requirements around informed consent.
CURRENT_CONSENT_VERSION = "v1"


class LeadStatus(models.TextChoices):
    NEW = "NEW", "New"
    CONTACTED = "CONTACTED", "Contacted"
    CONVERTED = "CONVERTED", "Converted to account"
    CLOSED = "CLOSED", "Closed / not proceeding"


class LeadTeachingModePreference(models.TextChoices):
    """
    Deliberately a separate, local choices class rather than importing
    apps.matching.StudentRequest.TeachingModePreference -- this app is
    the decoupled public front door (see module docstring) and doesn't
    otherwise depend on apps.matching at all. Codes are kept identical
    (HOME/ONLINE/ACADEMY/ANY) so staff converting a lead into a real
    StudentRequest can copy the value across directly.
    """

    ONLINE = "ONLINE", "Online"
    HOME = "HOME", "Home visit"
    ACADEMY = "ACADEMY", "Academy / coaching institute"
    ANY = "ANY", "Any of the above"


class ParentLead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(max_length=254, blank=True)
    
    area = models.CharField(max_length=100, help_text="Validated against active Area names at submission time.")

    student_class = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    preferred_timing = models.CharField(max_length=150, blank=True)

    # Captured from the marketing site's mode picker (Home/Online/
    # Academy/Any) -- previously collected in the UI but silently
    # dropped since this field didn't exist yet. Defaults to ANY so
    # staff triaging in admin still see a sensible value for leads
    # submitted before this field existed.
    teaching_mode_preference = models.CharField(
        max_length=10,
        choices=LeadTeachingModePreference.choices,
        default=LeadTeachingModePreference.ANY,
    )

    # DPDP consent, captured at the moment of submission on the public
    # marketing-site form -- this is the earliest point personal data
    # enters the system, so it's also the earliest point consent needs
    # to exist.
    consent_given = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, blank=True)

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
    email = models.EmailField(max_length=254, blank=True)
    area = models.CharField(max_length=100, help_text="Validated against active Area names at submission time.")

    subjects = models.CharField(max_length=255, blank=True)
    classes = models.CharField(max_length=255, blank=True)
    experience = models.CharField(max_length=100, blank=True)
    expected_fee = models.CharField(max_length=100, blank=True)

    consent_given = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=10, choices=LeadStatus.choices, default=LeadStatus.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leads_tutor_lead"
        indexes = [models.Index(fields=["status", "area"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.area}) - {self.status}"
