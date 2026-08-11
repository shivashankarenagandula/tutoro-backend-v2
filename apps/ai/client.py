"""
ai.client
----------
Phase 4 roadmap item 17: one shared, thin wrapper around an LLM SDK
that every AI feature in this codebase calls into, rather than each
feature (smart matching, bio generation, review moderation, FAQ
chatbot, semantic search, lead triage, area-page copy) reimplementing
its own client setup, model choice, and missing-key handling.

Provider: Google Gemini, via the `google-genai` SDK (the current
package -- NOT the older, now-legacy `google-generativeai` package,
which uses a different import path and API shape).

Design choices worth knowing before you touch this file:

  - GEMINI_API_KEY is read from settings, which reads it from the
    environment (see config/settings.py). If it's blank, every
    function here raises AIUnavailableError immediately rather than
    letting a request hang or fail with a confusing SDK error deep in
    a stack trace. Callers are expected to catch AIUnavailableError
    and degrade gracefully wherever an AI feature is an enhancement on
    top of working non-AI behavior (e.g. matching, search) -- see
    apps/matching/services.py::ai_rerank_by_notes for the pattern.
  - Model names, as of when this was written (Aug 2026): Gemini's
    lineup has been in genuine flux this year -- Gemini 3.5 Pro was
    announced in May 2026 and, as of this writing, still hasn't
    reached general availability after multiple delays. To avoid
    hardcoding a model name that might get deprecated or renamed
    without notice, both DEFAULT_MODEL and QUALITY_MODEL are
    overridable via environment variables (GEMINI_DEFAULT_MODEL /
    GEMINI_QUALITY_MODEL) without a code change -- see settings.py.
    They currently both default to gemini-3.6-flash (confirmed GA),
    since no Pro-tier model was confirmed stable at write time. Once
    a Pro-tier model is GA and you want higher-quality output for the
    two call sites that ask for QUALITY_MODEL explicitly (bio
    generation, area-page marketing copy), just set
    GEMINI_QUALITY_MODEL in the environment -- no code change needed.
  - The `google-genai` package is imported lazily inside _get_client(),
    not at module load time -- so importing this module (or any app
    that imports it) never fails just because the package happens to
    be missing in some environment; the failure only happens if an AI
    feature is actually invoked.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = getattr(settings, "GEMINI_DEFAULT_MODEL", "") or "gemini-3.6-flash"
# Used explicitly by the few call sites that need better prose quality
# than the default gives -- bio generation, area-page copy -- not the
# ranking/classification tasks, which stay on DEFAULT_MODEL. See the
# module docstring re: why this isn't hardcoded to a Pro-tier model.
QUALITY_MODEL = getattr(settings, "GEMINI_QUALITY_MODEL", "") or "gemini-3.6-flash"


class AIUnavailableError(RuntimeError):
    """
    Raised when an AI feature is invoked but GEMINI_API_KEY isn't
    configured. This is a normal, expected condition (e.g. local dev
    without a key) -- not a bug -- so it's its own exception type
    rather than a generic RuntimeError, letting callers catch
    specifically this and fall back to non-AI behavior without
    accidentally swallowing real errors too.
    """


def _get_client():
    if not settings.GEMINI_API_KEY:
        raise AIUnavailableError(
            "GEMINI_API_KEY is not set -- AI features are disabled until it is."
        )
    from google import genai  # noqa: local import, see module docstring

    return genai.Client(api_key=settings.GEMINI_API_KEY)


def complete(system, user, *, model=None, max_tokens=1024, temperature=0.4):
    """
    Plain-text completion. Returns the model's text response as a
    plain string.

    thinking_budget=0: Gemini 3.x models "think" (internal reasoning,
    not shown to the caller) before producing the visible answer by
    default, and that thinking consumes tokens from the SAME
    max_output_tokens budget as the answer itself. None of the tasks
    that call complete() (FAQ answers, classification, short prose)
    need multi-step reasoning -- without this, a low max_tokens value
    (e.g. 300 for a short FAQ answer) gets entirely consumed by
    invisible thinking, and the visible answer comes back truncated
    mid-sentence with no error raised, since the SDK call still
    "succeeds." This was the root cause of the FAQ chatbot cutting
    answers off after a few words.

    Raises:
      AIUnavailableError -- no API key configured.
      Whatever the `google-genai` SDK itself raises on an API-level
      failure (rate limit, timeout, etc.) -- deliberately NOT caught
      here, since this module doesn't know, per call site, whether a
      failure should degrade silently (matching re-rank) or surface
      to the user (an admin-triggered "generate bio" click). Callers
      decide that; see individual feature modules for the pattern.
    """
    from google.genai import types  # noqa: local import, see module docstring

    client = _get_client()
    response = client.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text or ""


def complete_json(system, user, *, model=None, max_tokens=1024, temperature=0.2):
    """
    Like complete(), but for call sites that asked the model (via
    their own `system` prompt instructions) to respond with JSON.
    Uses Gemini's native response_mime_type='application/json' mode
    (more reliable than asking nicely in the prompt and hoping), but
    still strips a stray ```json fence defensively in case the model
    adds one anyway -- this happened occasionally enough in practice
    to be worth the one extra check.

    Raises ValueError (not json.JSONDecodeError directly) if parsing
    fails, so callers can catch one clear exception type regardless of
    exactly how the model's output was malformed.
    """
    from google.genai import types  # noqa: local import, see module docstring

    client = _get_client()
    response = client.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    raw = response.text or ""
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
