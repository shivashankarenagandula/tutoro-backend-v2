"""
matching.management.commands.send_demo_reminders
----------------------------------------------------
Phase 5 item 27: auto-remind before scheduled demo classes.

Deliberately a management command run on a schedule (Render Cron Job),
not a Celery periodic task -- this project has no Celery/Redis
(see apps.leads.signals for the same reasoning re: notifications),
and a command you can also run by hand (`python manage.py
send_demo_reminders`) is easier to test/debug than a task queue entry.

Suggested Render Cron Job schedule: every 15-30 minutes,
`*/15 * * * *`, command: `python manage.py send_demo_reminders`.

Idempotent by design: DemoClass.reminder_sent is set True as soon as
a reminder attempt is made for that row, so running this command
twice in a row (or every 15 minutes) never double-sends. If a demo
gets rescheduled to a new time, reset reminder_sent=False on that row
(e.g. from the admin) so it gets a fresh reminder for the new time.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.notifications.services import send_whatsapp_message
from apps.matching.models import DemoClass

# How far ahead to look for demos needing a reminder. A demo scheduled
# further out than this simply isn't due for a reminder yet -- the
# next scheduled run of this command will pick it up once it falls
# inside the window.
REMINDER_WINDOW_HOURS = 3


class Command(BaseCommand):
    help = "Send a reminder (email + WhatsApp) for demo classes scheduled within the next few hours."

    def handle(self, *args, **options):
        now = timezone.now()
        window_end = now + timedelta(hours=REMINDER_WINDOW_HOURS)

        due_demos = (
            DemoClass.objects.filter(
                status=DemoClass.Status.SCHEDULED,
                reminder_sent=False,
                scheduled_at__gte=now,
                scheduled_at__lte=window_end,
            )
            .select_related(
                "assignment",
                "assignment__student_request",
                "assignment__student_request__parent__user",
                "assignment__tutor__user",
            )
        )

        sent_count = 0
        for demo in due_demos:
            assignment = demo.assignment
            student_request = assignment.student_request
            parent_user = student_request.parent.user
            tutor_user = assignment.tutor.user

            when = timezone.localtime(demo.scheduled_at).strftime("%d %b, %I:%M %p")
            link_line = f"\nJoin link: {demo.video_class_link}" if demo.video_class_link else ""

            parent_message = (
                f"Reminder: {student_request.student_name}'s demo class with "
                f"{assignment.tutor.full_name} is at {when}.{link_line}"
            )
            tutor_message = (
                f"Reminder: your demo class with {student_request.student_name} "
                f"is at {when}.{link_line}"
            )

            self._send_reminder(parent_user, parent_message)
            self._send_reminder(tutor_user, tutor_message)

            demo.reminder_sent = True
            demo.save(update_fields=["reminder_sent"])
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Sent reminders for {sent_count} demo class(es)."))

    def _send_reminder(self, user, message):
        # Best-effort on both channels -- a failure on one shouldn't
        # stop the other, and neither failure should stop the command
        # moving on to the next demo in the queue.
        if user.email:
            from django.conf import settings
            from django.core.mail import send_mail

            try:
                send_mail(
                    subject="Tutoro demo class reminder",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                pass

        if user.phone_number:
            try:
                send_whatsapp_message(user.phone_number, message)
            except Exception:
                pass
