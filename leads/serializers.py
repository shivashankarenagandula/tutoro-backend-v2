import re

from rest_framework import serializers

from apps.catalog.models import Area

from .models import ParentLead, TutorLead

# Matches a 10-digit Indian mobile number, optionally prefixed with
# +91, 91, or 0. Indian mobile numbers always start with 6-9.
PHONE_PATTERN = re.compile(r"^(?:\+91|91|0)?[6-9]\d{9}$")


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


def _validate_phone(value):
    """
    Format check only -- confirms the number LOOKS like a real Indian
    mobile number (10 digits, starts 6-9, no stray characters). This is
    NOT OTP verification -- it won't catch a valid-looking but wrong
    number. Given every lead gets a real phone call/WhatsApp from staff
    anyway, that's an acceptable tradeoff against the cost and signup
    friction of adding SMS OTP at this stage.
    """
    cleaned = value.strip().replace(" ", "").replace("-", "")
    if not PHONE_PATTERN.match(cleaned):
        raise serializers.ValidationError(
            "Please enter a valid 10-digit Indian mobile number."
        )
    # Normalize to a clean 10-digit form for storage, regardless of
    # whether they typed +91, 91, 0, or nothing in front.
    return re.sub(r"^(?:\+91|91|0)", "", cleaned)


class ParentLeadSerializer(serializers.ModelSerializer):
    # Honeypot: real humans never see or fill this field (hidden via CSS
    # on the frontend). Bots that auto-fill every field they find will
    # fill it, so any non-empty value here is a reliable spam signal.
    # write_only + not on the model -- never touches the database.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ParentLead
        fields = ["id", "name", "phone_number", "area", "student_class", "subject", "preferred_timing", "website"]
        read_only_fields = ["id"]

    def validate_area(self, value):
        return _validate_area_name(value)

    def validate_phone_number(self, value):
        return _validate_phone(value)

    def validate_website(self, value):
        if value:
            raise serializers.ValidationError("Spam detected.")
        return value

    def create(self, validated_data):
        validated_data.pop("website", None)
        return super().create(validated_data)


class TutorLeadSerializer(serializers.ModelSerializer):
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = TutorLead
        fields = ["id", "name", "phone_number", "area", "subjects", "classes", "experience", "expected_fee", "website"]
        read_only_fields = ["id"]

    def validate_area(self, value):
        return _validate_area_name(value)

    def validate_phone_number(self, value):
        return _validate_phone(value)

    def validate_website(self, value):
        if value:
            raise serializers.ValidationError("Spam detected.")
        return value

    def create(self, validated_data):
        validated_data.pop("website", None)
        return super().create(validated_data)
