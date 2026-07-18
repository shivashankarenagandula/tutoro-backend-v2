"""
leads.signals
--------------
Sends an instant email notification to the admin whenever a new
ParentLead or TutorLead is created.

Runs in a background thread rather than blocking the request -- a
parent submitting the demo-request form shouldn't have to wait for an
SMTP round-trip before seeing the success message. There's no
Celery/Redis here (deliberately, to stay on free hosting), so a plain
thread is the pragmatic middle ground: not as robust as a real task
queue, but correct for this volume and genuinely free.

If email isn't configured (EMAIL_HOST_USER blank), this silently does
nothing -- a missing notification should never be able to break lead
submission itself.
"""

import threading

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ParentLead, TutorLead


def _send_notification_email(subject, message):
    if not settings.EMAIL_HOST_USER or not settings.ADMIN_NOTIFICATION_EMAIL:
        return
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_NOTIFICATION_EMAIL],
            fail_silently=True,
        )
    except Exception:
        # Never let a notification failure surface as an error --
        # the lead is already safely saved by this point.
        pass


@receiver(post_save, sender=ParentLead)
def notify_new_parent_lead(sender, instance, created, **kwargs):
    if not created:
        return
    subject = f"New Tutoro lead: {instance.name} ({instance.area})"
    message = (
        f"New parent demo request.\n\n"
        f"Name: {instance.name}\n"
        f"Phone: {instance.phone_number}\n"
        f"Area: {instance.area}\n"
        f"Class: {instance.student_class}\n"
        f"Subject: {instance.subject}\n"
        f"Preferred timing: {instance.preferred_timing}\n"
    )
    threading.Thread(target=_send_notification_email, args=(subject, message), daemon=True).start()


@receiver(post_save, sender=TutorLead)
def notify_new_tutor_lead(sender, instance, created, **kwargs):
    if not created:
        return
    subject = f"New Tutoro tutor signup: {instance.name} ({instance.area})"
    message = (
        f"New tutor signup.\n\n"
        f"Name: {instance.name}\n"
        f"Phone: {instance.phone_number}\n"
        f"Area: {instance.area}\n"
        f"Subjects: {instance.subjects}\n"
        f"Classes: {instance.classes}\n"
        f"Experience: {instance.experience}\n"
        f"Expected fee: {instance.expected_fee}\n"
    )
    threading.Thread(target=_send_notification_email, args=(subject, message), daemon=True).start()
