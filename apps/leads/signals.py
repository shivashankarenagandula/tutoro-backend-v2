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

Also: Phase 4 item 24, duplicate-lead flagging (see
flag_duplicate_parent_lead / flag_duplicate_tutor_lead below).
"""

import threading
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import LeadStatus, ParentLead, TutorLead

# How far back to look for a matching phone/email when flagging a
# possible duplicate. Long enough to catch someone re-submitting the
# same form a few times in frustration or a script spamming leads;
# short enough that a parent who's a genuine repeat customer six
# months later isn't flagged as suspicious.
DUPLICATE_LOOKBACK_DAYS = 30


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


def _find_recent_duplicate(model, instance):
    """
    Exact match on phone number (or, failing that, email) against other
    leads of the SAME type submitted within DUPLICATE_LOOKBACK_DAYS --
    rule-based on purpose (see models.py comment on is_potential_duplicate
    for why this isn't an AI call). Excludes CLOSED leads: someone
    coming back after a closed-out lead isn't a fraud signal, they're
    a genuine repeat inquiry.
    """
    lookback_start = timezone.now() - timedelta(days=DUPLICATE_LOOKBACK_DAYS)
    recent = model.objects.filter(created_at__gte=lookback_start).exclude(pk=instance.pk).exclude(
        status=LeadStatus.CLOSED
    )

    phone_match = recent.filter(phone_number=instance.phone_number).order_by("created_at").first()
    if phone_match:
        return phone_match

    if instance.email:
        return recent.filter(email=instance.email).order_by("created_at").first()

    return None


@receiver(post_save, sender=ParentLead)
def flag_duplicate_parent_lead(sender, instance, created, **kwargs):
    if not created:
        return
    duplicate = _find_recent_duplicate(ParentLead, instance)
    if duplicate:
        # .update() rather than instance.save() -- doesn't re-fire
        # post_save, so there's no need to guard against a recursive
        # call into this same receiver.
        ParentLead.objects.filter(pk=instance.pk).update(
            is_potential_duplicate=True, duplicate_of=duplicate
        )


@receiver(post_save, sender=TutorLead)
def flag_duplicate_tutor_lead(sender, instance, created, **kwargs):
    if not created:
        return
    duplicate = _find_recent_duplicate(TutorLead, instance)
    if duplicate:
        TutorLead.objects.filter(pk=instance.pk).update(
            is_potential_duplicate=True, duplicate_of=duplicate
        )
