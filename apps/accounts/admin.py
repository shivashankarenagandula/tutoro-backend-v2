from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmailOTP, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "phone_number", "role", "is_verified", "is_active", "created_at"]
    list_filter = ["role", "is_verified", "is_active"]
    search_fields = ["email", "phone_number"]

    # AbstractUser's default fieldsets reference `username` — override
    # since we removed it, or Django admin will crash on this model.
    fieldsets = (
        (None, {"fields": ("email", "phone_number", "password")}),
        ("Role & status", {"fields": ("role", "is_verified", "is_active", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "phone_number", "password1", "password2", "role"),
        }),
    )


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    """
    Read-only -- this exists so support staff can see "did the code
    actually get generated / is it expired" when a user says
    verification isn't working, not to let anyone read or edit live
    codes from the admin.
    """

    list_display = ["user", "is_used", "created_at", "expires_at"]
    list_filter = ["is_used"]
    search_fields = ["user__email"]
    readonly_fields = ["id", "user", "code", "created_at", "expires_at", "is_used"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
