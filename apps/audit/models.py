"""
audit.models
-------------
SECURITY ADDITION — not in your original spec, but flagging it per
"find security issues" / "find missing features": a two-sided
marketplace with staff-mediated matching needs a record of who did
what, especially for:
  - which admin verified/rejected a tutor
  - which admin created/edited a match
  - any status change on payments

Without this, a dispute ("why was my tutor account rejected?") has no
paper trail. This is intentionally generic (action + model + object id
as a string) rather than one table per action type, so adding new
auditable actions later never needs a migration.
"""

import uuid

from django.db import models

from apps.accounts.models import User


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        VERIFY = "VERIFY", "Verify"
        REJECT = "REJECT", "Reject"
        MATCH = "MATCH", "Match created"
        LOGIN = "LOGIN", "Login"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_actions"
    )
    action = models.CharField(max_length=10, choices=Action.choices)

    # Generic reference instead of a FK to every possible model —
    # keeps this table decoupled from schema changes elsewhere.
    target_model = models.CharField(max_length=100, help_text="e.g. 'TutorProfile'")
    target_id = models.CharField(max_length=64)

    metadata = models.JSONField(
        default=dict, blank=True, help_text="Extra context, e.g. {'old_status': 'PENDING', 'new_status': 'VERIFIED'}"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_log"
        indexes = [
            models.Index(fields=["target_model", "target_id"]),
            models.Index(fields=["actor", "created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.actor} {self.action} {self.target_model}:{self.target_id}"
