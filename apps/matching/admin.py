from django.contrib import admin

from .models import Assignment, DemoClass, StudentRequest


@admin.register(StudentRequest)
class StudentRequestAdmin(admin.ModelAdmin):
    list_display = ["student_name", "student_class", "area", "status", "created_at"]
    list_filter = ["status", "student_class", "board", "area"]
    search_fields = ["student_name", "parent__full_name", "parent__user__phone_number"]
    autocomplete_fields = ["parent", "area", "subjects"]


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ["student_request", "tutor", "status", "matched_by", "created_at"]
    list_filter = ["status"]
    autocomplete_fields = ["student_request", "tutor", "matched_by"]


@admin.register(DemoClass)
class DemoClassAdmin(admin.ModelAdmin):
    list_display = ["assignment", "scheduled_at", "status"]
    list_filter = ["status"]
