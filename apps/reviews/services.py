"""
reviews.services
------------------
Phase 4 item 20: AI review moderation.

Deliberately assistive, not autonomous: moderate_review() only ever
sets ai_moderation_status + ai_moderation_notes. Whether a review
actually goes live is still is_published, set exclusively by a human
via ReviewPublishView or the Django admin -- an AI mistake here can
make staff double-check a fine review, never publish a bad one
un-reviewed. See models.Review.ModerationStatus for the status values.
"""

import json
import logging

from apps.ai.client import complete_json

from .models import Review

logger = logging.getLogger(__name__)


def moderate_review(review):
    """
    Runs once, right after a review is submitted (see
    ReviewCreateView.create). Never raises -- a moderation failure
    (missing API key, API error, bad JSON back) leaves the review at
    ai_moderation_status=SKIPPED/PENDING rather than blocking
    submission, since a parent's review going through is more
    important than the moderation pass succeeding synchronously.
    """
    system = (
        "You are a content-moderation assistant for a tutoring marketplace. "
        "Given a star rating and a comment, decide if the review needs staff "
        "attention before being published: spam/gibberish, hate speech or "
        "harassment, personal contact info (phone/email) that shouldn't be "
        "public, or a comment that clearly contradicts its own star rating "
        "(e.g. 1 star but the comment praises the tutor) are all reasons to "
        'flag. Respond with ONLY this JSON object: {"flagged": true|false, '
        '"reason": "one short sentence, empty string if not flagged"}. '
        "No markdown fences, no other keys."
    )
    user_prompt = json.dumps({"rating": review.rating, "comment": review.comment})

    try:
        result = complete_json(system, user_prompt, max_tokens=200)
    except Exception:  # noqa: broad -- moderation must never block submission
        logger.info("AI review moderation unavailable for review %s", review.id)
        review.ai_moderation_status = Review.ModerationStatus.SKIPPED
        review.save(update_fields=["ai_moderation_status"])
        return

    if not isinstance(result, dict) or "flagged" not in result:
        review.ai_moderation_status = Review.ModerationStatus.SKIPPED
        review.save(update_fields=["ai_moderation_status"])
        return

    if result.get("flagged"):
        review.ai_moderation_status = Review.ModerationStatus.FLAGGED
        review.ai_moderation_notes = str(result.get("reason", ""))[:500]
    else:
        review.ai_moderation_status = Review.ModerationStatus.OK
        review.ai_moderation_notes = ""

    review.save(update_fields=["ai_moderation_status", "ai_moderation_notes"])
