"""
Creates the admin superuser from environment variables, OR — if it
already exists — resets its password to match ADMIN_PASSWORD.

Why "sync" instead of just "create once": Render's free tier has no
Shell/SSH access, so if you ever forget the password or change
ADMIN_PASSWORD in the dashboard, there's no way to run
`changepassword` manually. Making this command sync on every deploy
means changing the env var and redeploying is always enough to fix
login -- the env var is the single source of truth, every time.

Usage: set ADMIN_EMAIL, ADMIN_PHONE, ADMIN_PASSWORD in Render's
Environment tab. Runs automatically via the Procfile/render.yaml
release command on every deploy.
"""

import os

from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create or sync the admin superuser from ADMIN_EMAIL/ADMIN_PHONE/ADMIN_PASSWORD env vars."

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL")
        phone = os.environ.get("ADMIN_PHONE")
        password = os.environ.get("ADMIN_PASSWORD")

        if not all([email, phone, password]):
            self.stdout.write(self.style.WARNING(
                "ADMIN_EMAIL / ADMIN_PHONE / ADMIN_PASSWORD not all set -- skipping admin creation."
            ))
            return

        user, created = User.objects.get_or_create(
            email__iexact=email,
            defaults={"email": email, "phone_number": phone, "role": User.Role.ADMIN},
        )

        # Always sync these, whether just-created or pre-existing --
        # this is what makes a Render env var change actually take effect.
        user.email = email
        user.phone_number = phone
        user.is_staff = True
        user.is_superuser = True
        user.role = User.Role.ADMIN
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Admin '{email}' created."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Admin '{email}' already existed -- password/role synced."))
