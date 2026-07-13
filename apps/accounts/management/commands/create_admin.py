
"""
Creates (or leaves alone) an admin superuser from environment variables.

Why this exists: Render's free tier has no Shell/SSH access, so the
normal `python manage.py createsuperuser` interactive prompt is
unreachable without upgrading to a paid plan. This command reads the
same information from env vars instead, and — critically — is
idempotent: safe to run on every single deploy, since it checks for
an existing user first rather than erroring out on the second run.

Usage: set ADMIN_EMAIL, ADMIN_PHONE, ADMIN_PASSWORD in Render's
Environment tab, then this runs automatically via the Procfile/
render.yaml release command on every deploy.
"""

import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create the admin superuser from ADMIN_EMAIL/ADMIN_PHONE/ADMIN_PASSWORD env vars, if it doesn't already exist."

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL")
        phone = os.environ.get("ADMIN_PHONE")
        password = os.environ.get("ADMIN_PASSWORD")

        if not all([email, phone, password]):
            self.stdout.write(self.style.WARNING(
                "ADMIN_EMAIL / ADMIN_PHONE / ADMIN_PASSWORD not all set -- skipping admin creation."
            ))
            return

        if User.objects.filter(email__iexact=email).exists():
            self.stdout.write(self.style.SUCCESS(f"Admin '{email}' already exists -- nothing to do."))
            return

        User.objects.create_superuser(email=email, phone_number=phone, password=password)
        self.stdout.write(self.style.SUCCESS(f"Admin '{email}' created."))
