"""
matching.services
------------------
Business logic lives here, separate from views, so the matching
algorithm can be unit-tested and reused (e.g. from a future admin
dashboard action or a management command) without going through HTTP.

Phase 2 update -- now branches by StudentRequest.teaching_mode_preference,
since a request can now be for a home-visit tutor, an online tutor, or
a referral to a partner Academy, and these three pools don't overlap:

  HOME    -> TutorProfile pool, filtered to teaching_mode HOME/BOTH,
             ranked same-area-first (the original area-first requirement
             still applies here, since a home tutor has to actually
             travel to the student).
  ONLINE  -> TutorProfile pool, filtered to teaching_mode ONLINE/BOTH.
             Area is irrelevant for a video call, so it's dropped from
             ranking entirely rather than kept as a no-op tiebreaker.
  ACADEMY -> a completely different table (Academy, not TutorProfile).
             Returns Academy candidates instead of tutors -- callers
             need to check .mode on the result to know which shape
             they're dealing with.
  ANY     -> tries HOME first, falls back to ONLINE, falls back to
             ACADEMY, returning the first pool that has *any* candidates
             rather than merging all three into one ranked list -- an
             "any mode" parent still needs one coherent list to review,
             not eligible-online-tutors interleaved with home tutors
             they can't actually compare on the same terms.
"""

import json

from apps.catalog.models import Academy
from apps.profiles.models import TutorProfile

from apps.ai.client import complete_json


def _suggest_home_tutors(student_request, limit):
    base_qs = TutorProfile.objects.filter(
        verification_status=TutorProfile.VerificationStatus.VERIFIED,
        is_accepting_students=True,
        subjects__in=student_request.subjects.all(),
        teaching_mode__in=[TutorProfile.TeachingMode.HOME, TutorProfile.TeachingMode.BOTH],
    ).distinct()

    same_area_qs = base_qs.filter(preferred_areas=student_request.area).order_by("-rating_avg")
    same_area_ids = set(same_area_qs.values_list("id", flat=True))

    other_area_qs = base_qs.exclude(id__in=same_area_ids).order_by("-rating_avg")

    ranked = list(same_area_qs) + list(other_area_qs)
    return ranked[:limit], same_area_ids


def _suggest_online_tutors(student_request, limit):
    # No area filtering/ranking at all -- distance is meaningless for a
    # video call, so same_area_ids is always empty here (kept in the
    # return shape so callers/serializers don't need a special case).
    base_qs = (
        TutorProfile.objects.filter(
            verification_status=TutorProfile.VerificationStatus.VERIFIED,
            is_accepting_students=True,
            subjects__in=student_request.subjects.all(),
            teaching_mode__in=[TutorProfile.TeachingMode.ONLINE, TutorProfile.TeachingMode.BOTH],
        )
        .distinct()
        .order_by("-rating_avg")
    )
    return list(base_qs[:limit]), set()


def _suggest_academies(student_request, limit):
    class_code = student_request.student_class
    base_qs = (
        Academy.objects.filter(
            is_active=True,
            areas_covered=student_request.area,
            subjects__in=student_request.subjects.all(),
        )
        .distinct()
    )
    # classes_offered is a comma-separated CharField (see Academy model
    # docstring), not a relation, so it can't be filtered in the query
    # itself -- checked here instead, same pattern as the model already
    # uses it for.
    results = [
        academy for academy in base_qs
        if not academy.classes_offered or class_code in academy.classes_offered.split(",")
    ]
    return results[:limit]


def ai_rerank_by_notes(student_request, candidates):
    """
    Phase 4 item 18: re-rank an already rule-filtered tutor list by how
    well each tutor's bio matches the parent's free-text notes.

    Deliberately a re-rank, not a re-filter: suggest_tutors_for_request()
    above still owns every hard rule (verified, accepting students,
    right subject/mode/area) -- this only reorders within a set that's
    already valid, so an AI mistake can make a good match rank lower,
    never surface an unqualified tutor.

    Returns `candidates` unchanged, in the same order, if: there are no
    notes to weigh, fewer than 2 candidates (nothing to reorder), no
    GEMINI_API_KEY is configured, or the AI call fails or returns
    something we can't trust (missing/extra ids). Re-ranking is a
    quality enhancement layered on top of working rule-based matching,
    never a hard dependency for suggestions to return results -- so a
    broad except here is intentional, not sloppy: any AI-layer failure
    must fall back silently rather than break the core suggestion flow
    a parent is waiting on.
    """
    if not student_request.notes or len(candidates) < 2:
        return candidates

    tutor_summaries = [
        {"id": str(tutor.id), "bio": (tutor.bio or "")[:500], "qualification": tutor.qualification}
        for tutor in candidates
    ]
    system = (
        "You rank tutor candidates for a tutoring marketplace by how well each "
        "tutor's bio and qualification match a parent's free-text notes about "
        "what their child needs. Respond with ONLY a JSON array of tutor id "
        "strings, best match first, including every id you were given exactly "
        "once. No prose, no markdown fences, no extra keys."
    )
    user_payload = {
        "parent_notes": student_request.notes,
        "tutors": tutor_summaries,
    }

    try:
        ranked_ids = complete_json(system, json.dumps(user_payload), max_tokens=500)
    except Exception:  # noqa: broad -- see docstring; any AI-layer failure must fall back
        return candidates

    if not isinstance(ranked_ids, list):
        return candidates

    by_id = {str(tutor.id): tutor for tutor in candidates}
    reranked = [by_id[tutor_id] for tutor_id in ranked_ids if tutor_id in by_id]
    # If the model dropped or invented an id, the counts won't match --
    # fall back rather than silently return an incomplete/malformed list.
    if len(reranked) != len(candidates):
        return candidates
    return reranked


def suggest_tutors_for_request(student_request, limit=10, use_ai_ranking=True):
    """
    Returns (results, same_area_ids, mode) for a given StudentRequest.

    `mode` tells the caller which pool `results` actually came from
    (HOME/ONLINE/ACADEMY) -- required for ANY, where the branch actually
    taken isn't knowable in advance from the request alone. Serializers
    and views should switch on `mode` to pick TutorSuggestionSerializer
    vs. an Academy-shaped serializer.

    `use_ai_ranking=False` is there for callers that want the pure
    rule-based order (e.g. tests asserting exact rule behavior, or a
    future admin "show me the raw ranking" toggle) without needing to
    know ai_rerank_by_notes exists at all.
    """
    preference = student_request.teaching_mode_preference
    Mode = student_request.TeachingModePreference

    if preference == Mode.HOME:
        results, same_area_ids = _suggest_home_tutors(student_request, limit)
        if use_ai_ranking:
            results = ai_rerank_by_notes(student_request, results)
        return results, same_area_ids, Mode.HOME

    if preference == Mode.ONLINE:
        results, same_area_ids = _suggest_online_tutors(student_request, limit)
        if use_ai_ranking:
            results = ai_rerank_by_notes(student_request, results)
        return results, same_area_ids, Mode.ONLINE

    if preference == Mode.ACADEMY:
        # Academies have no bio to weigh notes against -- AI re-ranking
        # doesn't apply to this pool at all, by design, not an oversight.
        return _suggest_academies(student_request, limit), set(), Mode.ACADEMY

    # ANY -- try each pool in order, return the first with results.
    home_results, home_same_area_ids = _suggest_home_tutors(student_request, limit)
    if home_results:
        if use_ai_ranking:
            home_results = ai_rerank_by_notes(student_request, home_results)
        return home_results, home_same_area_ids, Mode.HOME

    online_results, online_same_area_ids = _suggest_online_tutors(student_request, limit)
    if online_results:
        if use_ai_ranking:
            online_results = ai_rerank_by_notes(student_request, online_results)
        return online_results, online_same_area_ids, Mode.ONLINE

    return _suggest_academies(student_request, limit), set(), Mode.ACADEMY
