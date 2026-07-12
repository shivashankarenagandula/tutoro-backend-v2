"""
notifications.models
----------------------
In-app / WhatsApp / email notification log. Kept as a single table
with a `notification_type` discriminator rather than separate tables
per channel — most queries are "show me this user's unread
notifications," which is simplest against one table.
"""

import uuid

from django.db import models

from apps.accounts.models import User


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_MATCH = "NEW_MATCH", "New match proposed"
        DEMO_REMINDER = "DEMO_REMINDER", "Demo class reminder"
        REQUEST_UPDATE = "REQUEST_UPDATE", "Student request status update"
        PAYMENT = "PAYMENT", "Payment related"
        SYSTEM = "SYSTEM", "System message"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")

    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_notification"
        indexes = [models.Index(fields=["recipient", "is_read"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.notification_type} -> {self.recipient.email}"
