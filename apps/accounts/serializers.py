"""
accounts.serializers
----------------------
Registration is split into two serializers (parent vs tutor) rather
than one generic "register" endpoint, because the two roles need
completely different profile fields at signup (a parent needs an area;
a tutor needs subjects, experience, fee). Each serializer creates the
User AND the profile in a single atomic transaction — a half-created
account (User exists, profile doesn't) is a real bug class we're
avoiding here on purpose.
"""

from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers

from apps.catalog.models import Area, StudentClass, Subject
from apps.profiles.models import ParentProfile, TutorProfile

from .models import User


def _get_or_create_subject(name):
    """
    Resolves a tutor-typed subject name (e.g. 'Maths') to a Subject
    row, reusing an existing one case-insensitively (so 'maths' and
    'Maths' don't create two catalog entries) and creating a new one
    otherwise. Subjects were previously picked from a fixed list, so
    this is what lets a tutor now type any subject freely while still
    landing in the shared catalog other parts of the app (matching,
    admin) rely on.
    """
    name = name.strip()
    existing = Subject.objects.filter(name__iexact=name).first()
    if existing:
        return existing

    base_slug = slugify(name) or "subject"
    slug = base_slug
    suffix = 1
    while Subject.objects.filter(slug=slug).exists():
        suffix += 1
        slug = f"{base_slug}-{suffix}"

    return Subject.objects.create(name=name, slug=slug)


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Deliberately has no validate_email existence check (unlike the
    register serializers above) -- returning a different response for
    "no account with that email" vs "code sent" is exactly how a
    password-reset endpoint leaks which emails are registered. The
    view always returns the same generic message regardless.
    """
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)


class ParentRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True, min_length=8)

    full_name = serializers.CharField(max_length=150)
    area = serializers.PrimaryKeyRelatedField(
        queryset=Area.objects.filter(is_active=True),
        error_messages={
            "does_not_exist": "That area isn't currently supported by Tutoro."
        },
    )
    address_line = serializers.CharField(max_length=255, required=False, allow_blank=True)
    pincode = serializers.CharField(max_length=10, required=False, allow_blank=True)

    # Optional context about what the parent is looking for, captured
    # once at signup instead of forcing it into a second step -- see
    # ParentProfile.student_class/budget_fee/preferred_* for why these
    # live alongside the account rather than only on StudentRequest.
    student_class = serializers.ChoiceField(
        choices=StudentClass.choices, required=False, allow_blank=True, default=""
    )
    budget_fee = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    preferred_start_time = serializers.TimeField(required=False, allow_null=True, default=None)
    preferred_end_time = serializers.TimeField(required=False, allow_null=True, default=None)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            password=validated_data["password"],
            role=User.Role.PARENT,
        )
        profile = ParentProfile.objects.create(
            user=user,
            full_name=validated_data["full_name"],
            area=validated_data["area"],
            address_line=validated_data.get("address_line", ""),
            pincode=validated_data.get("pincode", ""),
            student_class=validated_data.get("student_class", ""),
            budget_fee=validated_data.get("budget_fee", ""),
            preferred_start_time=validated_data.get("preferred_start_time"),
            preferred_end_time=validated_data.get("preferred_end_time"),
        )
        return profile


class TutorRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True, min_length=8)

    full_name = serializers.CharField(max_length=150)
    # Free text, typed by the tutor (e.g. "Maths, Physics") rather than
    # picked from a fixed catalog list -- see _get_or_create_subject
    # above for how each name is resolved to (or added to) the shared
    # Subject catalog.
    subjects = serializers.ListField(
        child=serializers.CharField(max_length=100, allow_blank=False, trim_whitespace=True),
        allow_empty=False,
        error_messages={"empty": "Enter at least one subject you teach."},
    )
    preferred_areas = serializers.PrimaryKeyRelatedField(
        queryset=Area.objects.filter(is_active=True), many=True,
        error_messages={"does_not_exist": "One of those areas isn't currently supported by Tutoro."},
    )
    experience_years = serializers.IntegerField(required=False, default=0, min_value=0)
    qualification = serializers.CharField(max_length=200, required=False, allow_blank=True)
    teaching_mode = serializers.ChoiceField(
        choices=TutorProfile.TeachingMode.choices, default=TutorProfile.TeachingMode.HOME
    )
    fee_type = serializers.ChoiceField(
        choices=TutorProfile.FeeType.choices, default=TutorProfile.FeeType.PER_HOUR
    )
    online_fee = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    home_visit_fee = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    # The signup form's "Expected fee" field is a single generic input --
    # it doesn't ask the tutor to split it by teaching mode at signup
    # time (that split happens later on the full profile). Accepting it
    # here and applying it to whichever of online_fee/home_visit_fee
    # wasn't explicitly set (see create() below) means a tutor who fills
    # in this one field actually gets it saved, instead of it being
    # silently dropped as an unrecognized key.
    expected_fee = serializers.DecimalField(
        max_digits=8, decimal_places=2, required=False, allow_null=True,
        help_text="Generic fee from the signup form; backfills online_fee/home_visit_fee if those aren't set separately.",
    )

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_subjects(self, value):
        # Dedupe case-insensitively (e.g. "Maths" and "maths" typed as
        # two list entries) while preserving the tutor's original
        # casing for whichever occurrence comes first.
        seen = set()
        cleaned = []
        for name in value:
            name = name.strip()
            key = name.lower()
            if name and key not in seen:
                seen.add(key)
                cleaned.append(name)
        if not cleaned:
            raise serializers.ValidationError("Enter at least one subject you teach.")
        return cleaned

    def validate_preferred_areas(self, value):
        if not value:
            raise serializers.ValidationError("Select at least one area you can cover.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        subject_names = validated_data.pop("subjects")
        subjects = [_get_or_create_subject(name) for name in subject_names]
        preferred_areas = validated_data.pop("preferred_areas")

        # Backfill: if the tutor only filled in the single generic
        # "expected fee" field (the current signup form), apply it to
        # whichever of online_fee/home_visit_fee wasn't given explicitly,
        # so simple signups still end up with a usable fee on the
        # profile instead of losing it entirely.
        expected_fee = validated_data.pop("expected_fee", None)
        online_fee = validated_data.get("online_fee")
        home_visit_fee = validated_data.get("home_visit_fee")
        if expected_fee is not None:
            if online_fee is None:
                online_fee = expected_fee
            if home_visit_fee is None:
                home_visit_fee = expected_fee

        user = User.objects.create_user(
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            password=validated_data["password"],
            role=User.Role.TUTOR,
        )
        profile = TutorProfile.objects.create(
            user=user,
            full_name=validated_data["full_name"],
            experience_years=validated_data.get("experience_years", 0),
            qualification=validated_data.get("qualification", ""),
            teaching_mode=validated_data.get("teaching_mode", TutorProfile.TeachingMode.HOME),
            fee_type=validated_data.get("fee_type", TutorProfile.FeeType.PER_HOUR),
            online_fee=online_fee,
            home_visit_fee=home_visit_fee,
            # Every tutor starts PENDING — verification is a separate,
            # deliberate admin action, never automatic on signup.
            verification_status=TutorProfile.VerificationStatus.PENDING,
        )
        profile.subjects.set(subjects)
        profile.preferred_areas.set(preferred_areas)
        return profile
