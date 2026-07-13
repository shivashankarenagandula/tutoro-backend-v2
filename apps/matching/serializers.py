from rest_framework import serializers

from apps.catalog.models import Subject
from apps.profiles.models import TutorProfile

from .models import Assignment, DemoClass, StudentRequest


class StudentRequestSerializer(serializers.ModelSerializer):
    subjects = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True), many=True)
    parent_name = serializers.CharField(source="parent.full_name", read_only=True)
    area_name = serializers.CharField(source="area.name", read_only=True)

    class Meta:
        model = StudentRequest
        fields = [
            "id", "parent", "parent_name", "student_name", "student_class", "board",
            "subjects", "area", "area_name", "teaching_mode_preference",
            "preferred_timing", "budget_min", "budget_max", "status", "notes",
            "created_at",
        ]
        read_only_fields = ["id", "parent", "status", "created_at"]

    def validate_area(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Sorry, Tutoro isn't matching tutors in that area yet."
            )
        return value

    def validate_subjects(self, value):
        if not value:
            raise serializers.ValidationError("Select at least one subject.")
        return value

    def create(self, validated_data):
        subjects = validated_data.pop("subjects")
        # `parent` is never taken from client input — always the
        # logged-in user's own ParentProfile. See the view.
        validated_data["parent"] = self.context["request"].user.parent_profile
        student_request = StudentRequest.objects.create(**validated_data)
        student_request.subjects.set(subjects)
        return student_request


class TutorSuggestionSerializer(serializers.ModelSerializer):
    """Lightweight tutor summary used only in suggestion results — not
    the full TutorProfileSerializer, since an admin comparing candidates
    doesn't need every field, just enough to decide."""

    same_area = serializers.SerializerMethodField()

    class Meta:
        model = TutorProfile
        fields = [
            "id", "full_name", "experience_years", "rating_avg", "total_reviews",
            "fee_type", "expected_fee", "teaching_mode", "same_area",
        ]

    def get_same_area(self, obj):
        return obj.id in self.context.get("same_area_ids", set())


class AssignmentSerializer(serializers.ModelSerializer):
    tutor_name = serializers.CharField(source="tutor.full_name", read_only=True)
    student_name = serializers.CharField(source="student_request.student_name", read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "id", "student_request", "student_name", "tutor", "tutor_name",
            "matched_by", "status", "started_at", "ended_at", "end_reason", "created_at",
        ]
        read_only_fields = ["id", "matched_by", "created_at"]

    def create(self, validated_data):
        validated_data["matched_by"] = self.context["request"].user
        assignment = Assignment.objects.create(**validated_data)
        # Keep the parent's request in sync with the match being made.
        assignment.student_request.status = StudentRequest.Status.MATCHED
        assignment.student_request.save(update_fields=["status"])
        return assignment


class DemoClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = DemoClass
        fields = [
            "id", "assignment", "scheduled_at", "completed_at", "status",
            "feedback_from_parent", "feedback_from_tutor", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
