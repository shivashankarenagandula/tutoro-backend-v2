"""
payments.models
-----------------
Schema for Stage 2 monetization. Not wired to a payment gateway yet —
`gateway_reference` is where you'd store the Razorpay/Stripe
transaction ID once integrated.

Tied to Assignment (not StudentRequest) because billing only makes
sense once a real match exists — you can't charge commission on a
request nobody's been matched to yet.
"""

import uuid

from django.db import models

from apps.accounts.models import User
from apps.matching.models import Assignment


class Payment(models.Model):
    class PaymentType(models.TextChoices):
        COMMISSION = "COMMISSION", "Platform commission"
        SUBSCRIPTION = "SUBSCRIPTION", "Tutor subscription fee"
        TUTOR_PAYOUT = "TUTOR_PAYOUT", "Payout to tutor"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        Assignment, on_delete=models.PROTECT, related_name="payments"
    )
    payer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="payments_made")

    payment_type = models.CharField(max_length=20, choices=PaymentType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    # SECURITY NOTE: never store card numbers, CVVs, or full payment
    # details here. This field only stores the gateway's own
    # transaction/order ID for reconciliation — actual card data stays
    # entirely inside the payment gateway (Razorpay/Stripe), which is
    # PCI-DSS compliant so Tutoro's own database never has to be.
    gateway_reference = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments_payment"
        indexes = [models.Index(fields=["status", "payment_type"])]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.payment_type} - ₹{self.amount} ({self.status})"
