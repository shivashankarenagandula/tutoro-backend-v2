from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """
    Moderation is primarily expected to happen via the API
    (ReviewPublishView, for a future admin-dashboard UI / Phase 4 AI
    moderation), but a Django-admin fallback costs nothing and covers
    staff who just want to flip is_published directly today.
    """

    list_display = ["tutor", "reviewer", "rating", "is_published", "ai_moderation_status", "created_at"]
    list_filter = ["is_published", "ai_moderation_status", "rating"]
    list_editable = ["is_published"]
    search_fields = ["tutor__full_name", "reviewer__email", "comment"]
    readonly_fields = [
        "assignment", "reviewer", "tutor", "rating", "comment",
        "ai_moderation_status", "ai_moderation_notes", "created_at",
    ]
