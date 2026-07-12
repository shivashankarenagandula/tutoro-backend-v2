from django.contrib import admin

from .models import ParentProfile, TutorAvailability, TutorProfile


class TutorAvailabilityInline(admin.TabularInline):
    model = TutorAvailability
    extra = 1


@admin.register(TutorProfile)
class TutorProfileAdmin(admin.ModelAdmin):
    list_display = [
        "full_name", "verification_status", "is_accepting_students",
        "rating_avg", "total_reviews", "experience_years",
    ]
    list_filter = ["verification_status", "is_accepting_students", "teaching_mode"]
    search_fields = ["full_name", "user__email", "user__phone_number"]
    autocomplete_fields = ["user", "preferred_areas", "subjects", "verified_by"]
    inlines = [TutorAvailabilityInline]


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ["full_name", "area", "alternate_phone"]
    search_fields = ["full_name", "user__email", "user__phone_number"]
    autocomplete_fields = ["user", "area"]
