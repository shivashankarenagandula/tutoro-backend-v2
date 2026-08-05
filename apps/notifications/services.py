"""
notifications.services
------------------------
Outbound WhatsApp messages via Twilio's WhatsApp Business API.

Mirrors apps.leads.signals._send_notification_email exactly on
purpose: same "if not configured, silently no-op" philosophy, same
plain HTTP call (no SDK) to keep dependencies minimal, same "never let
a notification failure surface as an error" guarantee, since the
thing being notified about (a lead, a demo) is already safely saved
by the time this runs.

Twilio's Messages API is a plain REST endpoint authenticated with
HTTP Basic Auth (Account SID as username, Auth Token as password) --
no SDK needed, just `requests`.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TWILIO_MESSAGES_URL = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def send_whatsapp_message(to_number, body):
    """
    to_number: E.164 phone number WITHOUT the 'whatsapp:' prefix, e.g.
    '+919000000000' -- this function adds the prefix, so callers don't
    need to know about Twilio's formatting quirk.

    Returns True if the message was sent, False if it wasn't
    (including "not configured" -- callers generally don't need to
    branch on this, it's mainly useful for tests/management commands).
    """
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_WHATSAPP_FROM):
        return False

    url = TWILIO_MESSAGES_URL.format(sid=settings.TWILIO_ACCOUNT_SID)
    try:
        response = requests.post(
            url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data={
                "From": settings.TWILIO_WHATSAPP_FROM,
                "To": f"whatsapp:{to_number}",
                "Body": body,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            logger.warning("Twilio WhatsApp send failed (%s): %s", response.status_code, response.text)
            return False
        return True
    except requests.RequestException:
        # Never let a notification failure surface as an error -- the
        # underlying record (lead, demo class) is already saved.
        logger.exception("Twilio WhatsApp send raised an exception")
        return False


def notify_admin_whatsapp(body):
    """Convenience wrapper for the one recipient used everywhere
    right now (staff lead notifications). Silently does nothing if
    ADMIN_WHATSAPP_NUMBER isn't set, same as the Twilio creds check."""
    if not settings.ADMIN_WHATSAPP_NUMBER:
        return False
    # ADMIN_WHATSAPP_NUMBER is stored WITH the 'whatsapp:' prefix (to
    # match how it's usually copied straight from Twilio's console),
    # so strip it back off since send_whatsapp_message re-adds it.
    to_number = settings.ADMIN_WHATSAPP_NUMBER.replace("whatsapp:", "")
    return send_whatsapp_message(to_number, body)
