from django.contrib import admin

from .models import Academy, Area, City, Subject


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "is_active"]
    search_fields = ["name"]


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "is_active"]
    list_filter = ["city", "is_active"]
    search_fields = ["name"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["name"]


@admin.register(Academy)
class AcademyAdmin(admin.ModelAdmin):
    list_display = ["name", "contact_person", "contact_phone", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "contact_person", "contact_phone"]
    autocomplete_fields = ["areas_covered", "subjects"]
    fieldsets = (
        (None, {"fields": ("name", "is_active")}),
        ("Coverage", {"fields": ("areas_covered", "subjects", "classes_offered")}),
        ("Contact", {"fields": ("contact_person", "contact_phone", "contact_email")}),
        ("Referral terms", {"fields": ("referral_terms", "commission_percentage")}),
    )
