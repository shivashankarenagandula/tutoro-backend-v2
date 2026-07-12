"""
accounts.models
----------------
Custom User model. We do NOT use Django's default User because:
  1. We log in with email + phone, not a username.
  2. We need a `role` field for role-based access (parent / tutor / admin)
     across the whole platform.
  3. UUID primary keys avoid sequential-ID enumeration
     (e.g. someone incrementing /api/tutors/14/ to /15/ to scrape profiles).

SECURITY NOTE: never store raw passwords — AbstractUser + Django's
PBKDF2 password hasher (the default) handles this correctly as long as
you always go through `create_user()` / `set_password()`, never
`User(password="...")` directly.
"""

import uuid

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


phone_validator = RegexValidator(
    regex=r"^\+?91?\d{10}$",
    message="Phone number must be entered in the format: '+919876543210' or '9876543210'.",
)


class UserManager(BaseUserManager):
    """
    Custom manager since we removed `username` as the login field.
    Django's default UserManager assumes a username exists, so we
    override create_user / create_superuser to key off email instead.
    """

    use_in_migrations = True

    def _create_user(self, email, phone_number, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address.")
        if not phone_number:
            raise ValueError("Users must have a phone number.")
        email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone_number, password, **extra_fields)

    def create_superuser(self, email, phone_number, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, phone_number, password, **extra_fields)


class User(AbstractUser):
    """
    Base user for every person on the platform — parent, tutor, or admin.
    Profile-specific data (qualifications, child's class, etc.) lives in
    apps.profiles, NOT here — keeps this table lean and role-agnostic.
    """

    class Role(models.TextChoices):
        PARENT = "PARENT", _("Parent")
        TUTOR = "TUTOR", _("Tutor")
        ADMIN = "ADMIN", _("Admin")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # We don't use Django's username field at all.
    username = None
    email = models.EmailField(_("email address"), unique=True)
    phone_number = models.CharField(
        max_length=15, unique=True, validators=[phone_validator]
    )

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.PARENT)

    is_verified = models.BooleanField(
        default=False,
        help_text="Set True once phone/email OTP verification passes. "
        "Unverified users should have restricted actions (e.g. can't message).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["phone_number"]),
        ]

    def __str__(self):
        return f"{self.email} ({self.role})"
