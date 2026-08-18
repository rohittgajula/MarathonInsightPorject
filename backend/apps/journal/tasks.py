"""Background reading of daily logs.

The log must save instantly and must save when the API is unreachable or unkeyed —
what the athlete wrote is the record, and nothing about an optional enrichment may
put it at risk. So the write path stays synchronous with the keyword extractor, and
Claude runs after the fact, upgrading the row in place.

That ordering is also what makes a re-parse over history free to run: the same task,
pointed at old rows.
"""

from __future__ import annotations

import datetime as dt
import logging
import time

from celery import shared_task

from . import ai_extract
from .models import DailyLog

logger = logging.getLogger(__name__)


def _session_for(log: DailyLog):
    """The session prescribed on the day the log was written, for context only."""
    from apps.plans.models import Race
    from apps.plans.template import session_for

    race = Race.objects.filter(athlete=log.athlete, is_target=True).first()
    if race is None:
        return None
    return session_for(race.race_date, log.log_date, log.athlete)


def apply_analysis(log: DailyLog, data: dict) -> None:
    """Write a structured reading onto the row, without touching the text.

    The model's answer wins over the keyword extractor wherever it has one, and the
    keyword value is kept wherever the model said nothing — the two are additive, so
    a cautious model never erases something the regex already found.
    """
    log.ai_analysis = data
    log.ai_status = "done"
    log.ai_model = data.get("_model", "")
    log.extraction_version = data.get("_version", log.extraction_version)

    # Which day the entry is about. Clamped to ±1 day: the schema only offers those,
    # and a wider window would let one misreading move an entry somewhere the athlete
    # would never find it.
    offset = data.get("applies_to_offset_days")
    if isinstance(offset, int) and -1 <= offset <= 1:
        target = log.log_date + dt.timedelta(days=offset)
        log.applies_to_date = target if target != log.log_date else None
        log.applies_to_reason = (data.get("date_reason") or "")[:200] if offset else ""

    if data.get("sleep_hours") is not None:
        log.sleep_hours = data["sleep_hours"]
    if data.get("sleep_quality"):
        log.sleep_quality = data["sleep_quality"]
    if data.get("alcohol_units") is not None:
        log.alcohol_units = data["alcohol_units"]
    if data.get("felt"):
        log.felt = data["felt"]

    # Booleans are taken from the model outright rather than OR-ed with the keyword
    # pass: "not ill" is a real answer, and keeping a false positive from a regex
    # would mean the plan stays dropped for a word that appeared in passing.
    log.illness = bool(data.get("illness"))
    log.stressed = bool(data.get("stressed"))
    log.travel = bool(data.get("travel"))

    pains = data.get("pain") or []
    if pains:
        worst = max(pains, key=lambda p: p.get("severity") or 0)
        log.pain_area = worst.get("area") or ""
        log.pain_severity = worst.get("severity")
        log.pain_when = worst.get("when") or ""
    else:
        log.pain_area = ""
        log.pain_severity = None
        log.pain_when = ""

    # save() re-runs the keyword extractor over the text and would overwrite
    # everything set above, so the enriched fields are written directly instead.
    DailyLog.objects.filter(pk=log.pk).update(
        ai_analysis=log.ai_analysis, ai_status=log.ai_status, ai_model=log.ai_model,
        extraction_version=log.extraction_version,
        applies_to_date=log.applies_to_date, applies_to_reason=log.applies_to_reason,
        sleep_hours=log.sleep_hours, sleep_quality=log.sleep_quality,
        alcohol_units=log.alcohol_units, felt=log.felt,
        illness=log.illness, stressed=log.stressed, travel=log.travel,
        pain_area=log.pain_area, pain_severity=log.pain_severity, pain_when=log.pain_when,
    )


@shared_task
def analyse_log(log_id: int) -> str:
    """Read one log with Claude and upgrade the row. Never raises into the caller."""
    log = DailyLog.objects.select_related("athlete").filter(pk=log_id).first()
    if log is None:
        return "missing"

    if not ai_extract.configured():
        DailyLog.objects.filter(pk=log_id).update(ai_status="unavailable")
        return "unavailable"

    try:
        session = _session_for(log)
    except Exception:
        logger.exception("could not resolve session context for log %s", log_id)
        session = None

    try:
        data = ai_extract.analyse(log.text, log.athlete, log.log_date, session)
    except ai_extract.AuthFailed:
        DailyLog.objects.filter(pk=log_id).update(ai_status="bad_key")
        return "bad_key"
    except ai_extract.RateLimited:
        # Not read yet, rather than unreadable. `sweep_unread` retries it.
        DailyLog.objects.filter(pk=log_id).update(ai_status="rate_limited")
        return "rate_limited"

    if data is None:
        DailyLog.objects.filter(pk=log_id).update(ai_status="failed")
        return "failed"

    apply_analysis(log, data)
    return "done"


@shared_task
def reparse_logs(athlete_id: int | None = None, limit: int = 200) -> dict:
    """Re-read entries that predate the current extractor.

    This is the payoff for having stored the raw text since the first entry: a
    better reading can be applied to everything already written, rather than only to
    what comes next.
    """
    from django.db.models import Q

    stale = DailyLog.objects.filter(
        ~Q(ai_status="done") | Q(extraction_version__lt=ai_extract.AI_EXTRACTION_VERSION)
    )
    if athlete_id is not None:
        stale = stale.filter(athlete_id=athlete_id)

    # Gemini's free tier allows 20 requests a minute. Pacing here is cheaper than
    # relying on the retry inside the client: a re-parse is never urgent, and
    # arriving under the limit beats backing off after hitting it.
    gap = 3.5 if ai_extract.provider() == "gemini" else 0.0

    counts: dict[str, int] = {}
    for index, log_id in enumerate(stale.order_by("-log_date").values_list("pk", flat=True)[:limit]):
        if index and gap:
            time.sleep(gap)
        outcome = analyse_log(log_id)
        counts[outcome] = counts.get(outcome, 0) + 1
        # One unkeyed row means every row is unkeyed, and one exhausted quota means
        # every remaining row will exhaust it too. Stop rather than burning the rest
        # of the sweep discovering the same thing repeatedly.
        if outcome in ("unavailable", "rate_limited", "bad_key"):
            break
    return counts


@shared_task
def sweep_unread(limit: int = 25) -> dict:
    """Retry anything not yet read. Scheduled, so a spent quota heals itself.

    Without this, an entry written while the free tier is exhausted stays unread
    until someone notices and re-runs a task by hand — which nobody will.
    """
    return reparse_logs(limit=limit)
