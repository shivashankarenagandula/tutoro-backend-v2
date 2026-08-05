"""
leads.services
----------------
Phase 4 item 23: AI-assisted lead triage. Staff-triggered (a Django
admin action, see admin.py) rather than automatic on submission --
running this on every single lead the moment it arrives would mean
paying for an AI call on leads staff might close as spam a minute
later; triaging a batch staff have chosen to look at is both cheaper
and matches how staff actually work through a lead queue.
"""

import json
import logging

from apps.ai.client import complete_json

logger = logging.getLogger(__name__)

_VALID_PRIORITIES = {"HIGH", "MEDIUM", "LOW"}


def _describe_parent_lead(lead):
    return {
        "type": "parent",
        "area": lead.area,
        "student_class": lead.student_class,
        "subject": lead.subject,
        "preferred_timing": lead.preferred_timing,
        "teaching_mode_preference": lead.teaching_mode_preference,
        "is_potential_duplicate": lead.is_potential_duplicate,
    }


def _describe_tutor_lead(lead):
    return {
        "type": "tutor",
        "area": lead.area,
        "subjects": lead.subjects,
        "classes": lead.classes,
        "experience": lead.experience,
        "expected_fee": lead.expected_fee,
        "is_potential_duplicate": lead.is_potential_duplicate,
    }


def triage_lead(lead):
    """
    Sets lead.ai_priority and lead.ai_triage_notes in place (does not
    save -- callers batch-save, see admin.py action) based on how
    complete/specific/promising the lead's own fields are. This is
    about triage signal from the lead's content, NOT a judgment about
    the person -- e.g. a lead missing a subject or timing is lower
    priority because staff will need to call and ask before they can
    even suggest a tutor, not because of anything about the parent.

    Leaves ai_priority at its current value (typically UNSCORED) and
    logs a warning if the AI call fails or returns something
    unusable -- triage is a staff productivity aid, never something
    that should raise and interrupt an admin bulk action partway
    through a batch.
    """
    from .models import ParentLead

    description = _describe_parent_lead(lead) if isinstance(lead, ParentLead) else _describe_tutor_lead(lead)

    system = (
        "You triage inbound leads for a tutoring marketplace's staff queue. "
        "Score how promising and actionable a lead is based ONLY on the "
        "fields given -- a lead missing key details (subject, area, timing) "
        "is lower priority because staff can't act on it yet, not because "
        "of anything about the person. A lead already flagged as a possible "
        'duplicate should generally not be HIGH priority. Respond with ONLY '
        'this JSON object: {"priority": "HIGH"|"MEDIUM"|"LOW", "notes": '
        '"one short sentence explaining why"}. No markdown fences, no other keys.'
    )

    try:
        result = complete_json(system, json.dumps(description), max_tokens=200)
    except Exception:  # noqa: broad -- triage must never break the admin bulk action
        logger.info("AI lead triage unavailable for lead %s", lead.pk)
        return

    if not isinstance(result, dict):
        return
    priority = str(result.get("priority", "")).upper()
    if priority not in _VALID_PRIORITIES:
        return

    lead.ai_priority = priority
    lead.ai_triage_notes = str(result.get("notes", ""))[:500]
