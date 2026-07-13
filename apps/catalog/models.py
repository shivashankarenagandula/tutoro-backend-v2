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
