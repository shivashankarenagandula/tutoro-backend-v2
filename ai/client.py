"""
ai.client
----------
Phase 4 roadmap item 17: one shared, thin wrapper around the Anthropic
SDK that every AI feature in this codebase calls into, rather than
each feature (smart matching, bio generation, review moderation, FAQ
chatbot, semantic search, lead triage, area-page copy) reimplementing
its own client setup, model choice, and missing-key handling.

Design choices worth knowing before you touch this file:

  - ANTHROPIC_API_KEY is read from settings, which reads it from the
    environment (see config/settings.py). If it's blank, every
    function here raises AIUnavailableError immediately rather than
    letting a request hang or fail with a confusing SDK error deep in
    a stack trace. Callers are expected to catch AIUnavailableError
    and degrade gracefully wherever an AI feature is an enhancement on
    top of working non-AI behavior (e.g. matching, search) -- see
    apps/matching/services.py::ai_rerank_by_notes for the pattern.
  - Default model is Haiku (see DEFAULT_MODEL below), not Sonnet or
    Opus. Every Phase 4 use case sitting on top of this module is a
    small-context, low-latency task (ranking a handful of candidates,
    classifying a lead, moderating a short review) called
    synchronously inside a request/response cycle -- Haiku's quality
    is plenty for these and its cost/latency profile is what you
    actually want for something a user is waiting on. The two
    exceptions that benefit from more creative/higher-quality output
    (bio generation, area-page marketing copy) pass model=SONNET_MODEL
    explicitly at the call site.
  - The `anthropic` package is imported lazily inside _get_client(),
    not at module load time -- so importing this module (or any app
    that imports it) never fails just because the package happens to
    be missing in some environment; the failure only happens if an AI
    feature is actually invoked.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
# Used explicitly by the few call sites that need better prose quality
# than Haiku gives -- bio generation, area-page copy -- not the
# ranking/classification tasks, which stay on DEFAULT_MODEL.
SONNET_MODEL = "claude-sonnet-5"


class AIUnavailableError(RuntimeError):
    """
    Raised when an AI feature is invoked but ANTHROPIC_API_KEY isn't
    configured. This is a normal, expected condition (e.g. local dev
    without a key) -- not a bug -- so it's its own exception type
    rather than a generic RuntimeError, letting callers catch
    specifically this and fall back to non-AI behavior without
    accidentally swallowing real errors too.
    """


def _get_client():
    if not settings.ANTHROPIC_API_KEY:
        raise AIUnavailableError(
            "ANTHROPIC_API_KEY is not set -- AI features are disabled until it is."
        )
    import anthropic  # noqa: local import, see module docstring

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def complete(system, user, *, model=None, max_tokens=1024, temperature=0.4):
    """
    Plain-text completion. Returns the model's text response as a
    plain string.

    Raises:
      AIUnavailableError -- no API key configured.
      Whatever the `anthropic` SDK itself raises on an API-level
      failure (rate limit, timeout, etc.) -- deliberately NOT caught
      here, since this module doesn't know, per call site, whether a
      failure should degrade silently (matching re-rank) or surface
      to the user (an admin-triggered "generate bio" click). Callers
      decide that; see individual feature modules for the pattern.
    """
    client = _get_client()
    response = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def complete_json(system, user, *, model=None, max_tokens=1024, temperature=0.2):
    """
    Like complete(), but for call sites that asked the model (via
    their own `system` prompt instructions) to respond with JSON.
    Strips a ```json fence if the model added one anyway despite being
    told not to, then parses.

    Raises ValueError (not json.JSONDecodeError directly) if parsing
    fails, so callers can catch one clear exception type regardless of
    exactly how the model's output was malformed.
    """
    raw = complete(system, user, model=model, max_tokens=max_tokens, temperature=temperature)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as exc:
        logger.warning("AI JSON response failed to parse (first 500 chars): %s", raw[:500])
        raise ValueError(f"AI response wasn't valid JSON: {exc}") from exc
