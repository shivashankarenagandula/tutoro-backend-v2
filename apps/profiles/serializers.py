from rest_framework import serializers

from apps.catalog.models import Area, Subject

from .models import ParentProfile, TutorAvailability, TutorProfile


class ParentProfileSerializer(serializers.ModelSerializer):
    area_name = serializers.CharField(source="area.name", read_only=True)

    class Meta:
        model = ParentProfile
        fields = [
            "id", "full_name", "alternate_phone", "address_line",
            "area", "area_name", "pincode", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_area(self, value):
        if not value.is_active:
            raise serializers.ValidationError("That area isn't currently supported by Tutoro.")
        return value


class TutorAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TutorAvailability
        fields = ["id", "weekday", "start_time", "end_time"]


class TutorProfileSerializer(serializers.ModelSerializer):
    subjects = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.filter(is_active=True), many=True
    )
    preferred_areas = serializers.PrimaryKeyRelatedField(
        queryset=Area.objects.filter(is_active=True), many=True
    )
    availability_slots = TutorAvailabilitySerializer(many=True, read_only=True)

    class Meta:
        model = TutorProfile
        fields = [
            "id", "full_name", "bio", "qualification", "experience_years",
            "subjects", "preferred_areas", "teaching_mode", "fee_type",
            "expected_fee", "is_accepting_students", "verification_status",
            "rating_avg", "total_reviews", "availability_slots", "created_at",
        ]
        # A tutor can edit their own bio/fee/availability, but NOT their
        # own verification status — that's an admin-only action, done
        # through a separate endpoint below.
        read_only_fields = ["id", "verification_status", "rating_avg", "total_reviews", "created_at"]
