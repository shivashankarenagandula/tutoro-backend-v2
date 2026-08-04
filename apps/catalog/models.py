"""
catalog.models
--------------
Reference/lookup data: which city, which locality, which subjects exist.

Why City is separate from Area (and not just "Hyderabad" hardcoded
everywhere): the SEO locality pages already built for Tutoro
(Kukatpally, Madhapur, etc.) map directly onto Area rows. If Tutoro
expands to Bangalore or Chennai later, you add a City row and new Area
rows — zero model changes, zero migrations for new cities.
"""

import uuid

from django.db import models

from apps.accounts.models import phone_validator


class StudentClass(models.TextChoices):
    """
    Grade/level a student needs tutoring for. Lives in catalog (not
    matching) so both matching.StudentRequest and catalog.Academy can
    share one definition -- an Academy's "classes offered" and a
    StudentRequest's "student_class" need to speak the same values for
    AcademyReferral matching to ever compare them meaningfully.
    """

    C1_5 = "C1_5", "Class 1\u20135"
    C6_8 = "C6_8", "Class 6\u20138"
    C9_10 = "C9_10", "Class 9\u201310"
    C11_12 = "C11_12", "Class 11\u201312"
    DEGREE = "DEGREE", "Degree"
    COMPETITIVE = "COMPETITIVE", "Competitive Exam Prep"


class City(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    state = models.CharField(max_length=100, default="Telangana")
    slug = models.SlugField(max_length=120, unique=True)
    is_active = models.BooleanField(
        default=True, help_text="Turn off instead of deleting when a city is paused."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalog_city"
        verbose_name_plural = "cities"

    def __str__(self):
        return self.name


class Area(models.Model):
    """
    A locality within a city — Kukatpally, Madhapur, etc.
    Matches 1:1 with the SEO locality pages on the marketing site.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="areas")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120)
    pincode = models.CharField(max_length=10, blank=True)

    # Used for future distance-based matching (e.g. "tutor within 3km").
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "catalog_area"
        unique_together = [("city", "slug")]
        indexes = [models.Index(fields=["city", "is_active"])]
        verbose_name_plural = "areas"

    def __str__(self):
        return f"{self.name}, {self.city.name}"


class Subject(models.Model):
    class Category(models.TextChoices):
        ACADEMIC = "ACADEMIC", "Academic (school/college)"
        COMPETITIVE = "COMPETITIVE", "Competitive Exam (EAMCET, JEE, NEET…)"
        SKILL = "SKILL", "Skill-based (coding, music, etc.)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.ACADEMIC
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "catalog_subject"
        indexes = [models.Index(fields=["category", "is_active"])]

    def __str__(self):
        return self.name


class Academy(models.Model):
    """
    A partner coaching institute/academy that Tutoro refers ACADEMY-mode
    requests to, instead of (or alongside) an individual tutor.

    Deliberately NOT a TutorProfile subtype -- an academy isn't a person
    with a verification workflow, it's an external business Tutoro has
    a referral relationship with. Kept in catalog (reference data
    admins manage directly) rather than matching, mirroring how
    City/Area/Subject work.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=200)

    areas_covered = models.ManyToManyField(
        Area, related_name="academies", blank=True,
        help_text="Localities this academy serves or is reachable from.",
    )
    subjects = models.ManyToManyField(
        Subject, related_name="academies", blank=True,
    )
    # Free-text, comma-separated StudentClass codes (e.g. "C1_5,C6_8") --
    # not a M2M table since this is a small, rarely-queried set per
    # academy; matches the same "simple CharField for a short list"
    # pattern already used by apps.leads.TutorLead.classes.
    classes_offered = models.CharField(
        max_length=255, blank=True,
        help_text="Comma-separated StudentClass codes, e.g. 'C1_5,C6_8,C9_10'.",
    )

    contact_person = models.CharField(max_length=150, blank=True)
    contact_phone = models.CharField(max_length=15, blank=True, validators=[phone_validator])
    contact_email = models.EmailField(max_length=254, blank=True)

    # Free-text terms plus an optional structured percentage -- referral
    # deals vary enough (flat fee vs. % of first month vs. per-enrollment)
    # that forcing a single numeric field would lose information staff
    # actually need when following up.
    referral_terms = models.TextField(
        blank=True, help_text="Commission/referral agreement details, in plain language.",
    )
    commission_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Optional structured commission %, if the deal is a simple flat percentage.",
    )

    is_active = models.BooleanField(
        default=True, help_text="Turn off instead of deleting when a partnership pauses/ends.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "catalog_academy"
        indexes = [models.Index(fields=["is_active"])]
        verbose_name_plural = "academies"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def classes_offered_list(self):
        """Parsed list of StudentClass codes, for display/filtering."""
        return [c.strip() for c in self.classes_offered.split(",") if c.strip()]
