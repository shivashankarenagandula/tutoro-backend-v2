from rest_framework import serializers

from apps.catalog.models import Area

from .models import ParentLead, TutorLead


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


class ParentLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentLead
        fields = ["id", "name", "phone_number", "area", "student_class", "subject", "preferred_timing"]
        read_only_fields = ["id"]

    def validate_area(self, value):
        return _validate_area_name(value)


class TutorLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorLead
        fields = ["id", "name", "phone_number", "area", "subjects", "classes", "experience", "expected_fee"]
        read_only_fields = ["id"]

    def validate_area(self, value):
        return _validate_area_name(value)
