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
from rest_framework import serializers

from apps.catalog.models import Area, Subject
from apps.profiles.models import ParentProfile, TutorProfile

from .models import User


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
        )
        return profile


class TutorRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=15)
    password = serializers.CharField(write_only=True, min_length=8)

    full_name = serializers.CharField(max_length=150)
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True), many=True
    )
    preferred_areas = serializers.PrimaryKeyRelatedField(
        queryset=Area.objects.filter(is_active=True), many=True,
        error_messages={"does_not_exist": "One of those areas isn't currently supported by Tutoro."},
    )
    experience_years = serializers.IntegerField(required=False, default=0, min_value=0)
    qualification = serializers.CharField(max_length=200, required=False, allow_blank=True)
    teaching_mode = serializers.ChoiceField(
        choices=TutorProfile.TeachingMode.choices, default=TutorProfile.TeachingMode.OFFLINE
    )
    fee_type = serializers.ChoiceField(
        choices=TutorProfile.FeeType.choices, default=TutorProfile.FeeType.PER_HOUR
    )
    expected_fee = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_subjects(self, value):
        if not value:
            raise serializers.ValidationError("Select at least one subject you teach.")
        return value

    def validate_preferred_areas(self, value):
        if not value:
            raise serializers.ValidationError("Select at least one area you can cover.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        subjects = validated_data.pop("subjects")
        preferred_areas = validated_data.pop("preferred_areas")

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
            teaching_mode=validated_data.get("teaching_mode", TutorProfile.TeachingMode.OFFLINE),
            fee_type=validated_data.get("fee_type", TutorProfile.FeeType.PER_HOUR),
            expected_fee=validated_data.get("expected_fee"),
            # Every tutor starts PENDING — verification is a separate,
            # deliberate admin action, never automatic on signup.
            verification_status=TutorProfile.VerificationStatus.PENDING,
        )
        profile.subjects.set(subjects)
        profile.preferred_areas.set(preferred_areas)
        return profile
