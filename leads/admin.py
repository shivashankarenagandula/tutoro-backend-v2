from django.contrib import admin

from .models import ParentLead, TutorLead


@admin.register(ParentLead)
class ParentLeadAdmin(admin.ModelAdmin):
    list_display = ["name", "phone_number", "area", "subject", "status", "created_at"]
    list_filter = ["status", "area"]
    search_fields = ["name", "phone_number"]
    list_editable = ["status"]


@admin.register(TutorLead)
class TutorLeadAdmin(admin.ModelAdmin):
    list_display = ["name", "phone_number", "area", "subjects", "status", "created_at"]
    list_filter = ["status", "area"]
    search_fields = ["name", "phone_number"]
    list_editable = ["status"]
