from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import Area

from .models import CURRENT_CONSENT_VERSION, ParentLead, TutorLead


def _validate_area_name(value):
    """
    Shared validation: the submitted area text must match one of the
    currently active areas (case-insensitive). This is what actually
    enforces "parents/tutors can only submit for supported service
    areas" at the point of entry from the public website.
    """
    if not Area.objects.filter(is_active=True, name__iexact=value.strip()).exists():
        raise serializers.ValidationError(
            "Sorry, Tutoro isn't matching in that area yet. "
            "Please choose one of our current service areas."
        )
    return value.strip()


def _validate_consent(value):
    # DPDP consent is mandatory to submit at all -- not just a field we
    # happen to store. A lead form submitted with the box unchecked
    # should fail validation, not silently save consent_given=False.
    if not value:
        raise serializers.ValidationError(
            "Please agree to the privacy notice to submit this form."
        )
    return value


class ParentLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentLead
        fields = [
            "id", "name", "phone_number", "email", "area", "student_class",
            "subject", "preferred_timing", "teaching_mode_preference",
            "consent_given",
        ]
        read_only_fields = ["id"]

    def validate_area(self, value):
        return _validate_area_name(value)

    def validate_consent_given(self, value):
        return _validate_consent(value)

    def create(self, validated_data):
        validated_data["consent_given_at"] = timezone.now()
        validated_data["consent_version"] = CURRENT_CONSENT_VERSION
        return super().create(validated_data)


class TutorLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorLead
        fields = [
            "id", "name", "phone_number", "email", "area", "subjects",
            "classes", "experience", "expected_fee", "consent_given",
        ]
        read_only_fields = ["id"]

    def validate_area(self, value):
        return _validate_area_name(value)

    def validate_consent_given(self, value):
        return _validate_consent(value)

    def create(self, validated_data):
        validated_data["consent_given_at"] = timezone.now()
        validated_data["consent_version"] = CURRENT_CONSENT_VERSION
        return super().create(validated_data)
