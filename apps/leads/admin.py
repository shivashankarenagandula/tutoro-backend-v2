from django.contrib import admin

from .models import ParentLead, TutorLead
from .services import triage_lead


@admin.action(description="Run AI triage on selected leads")
def run_ai_triage(modeladmin, request, queryset):
    """
    Phase 4 item 23. Scores each selected lead's own ai_priority /
    ai_triage_notes in place, then bulk_updates -- one AI call per
    lead (see leads.services.triage_lead for why this is staff-
    triggered rather than automatic), but only one DB write for the
    whole batch.
    """
    leads = list(queryset)
    for lead in leads:
        triage_lead(lead)
    modeladmin.model.objects.bulk_update(leads, ["ai_priority", "ai_triage_notes"])
    modeladmin.message_user(request, f"Triaged {len(leads)} lead(s).")


@admin.register(ParentLead)
class ParentLeadAdmin(admin.ModelAdmin):
    list_display = [
        "name", "phone_number", "area", "subject", "teaching_mode_preference",
        "ai_priority", "is_potential_duplicate", "status", "created_at",
    ]
    list_filter = ["status", "area", "teaching_mode_preference", "ai_priority", "is_potential_duplicate"]
    search_fields = ["name", "phone_number"]
    list_editable = ["status"]
    readonly_fields = ["ai_priority", "ai_triage_notes", "is_potential_duplicate", "duplicate_of"]
    actions = [run_ai_triage]


@admin.register(TutorLead)
class TutorLeadAdmin(admin.ModelAdmin):
    list_display = [
        "name", "phone_number", "area", "subjects",
        "ai_priority", "is_potential_duplicate", "status", "created_at",
    ]
    list_filter = ["status", "area", "ai_priority", "is_potential_duplicate"]
    search_fields = ["name", "phone_number"]
    list_editable = ["status"]
    readonly_fields = ["ai_priority", "ai_triage_notes", "is_potential_duplicate", "duplicate_of"]
    actions = [run_ai_triage]
