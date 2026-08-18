"""What a log entry means, once something has read it.

`ai_extract` turns prose into facts. This turns facts into advice — in ordinary
Python, with thresholds that can be read, argued with, and tested. The model never
gets to decide any of it.

The division of labour matters most in the two cases the athlete asked for:

- "today I had biryani" → the model records a heavy, high-salt evening meal. *This*
  file knows that a high-salt meal the night before a hot-weather session raises the
  next morning's fluid need, and by how much.
- "pain in my feet while running" → the model records area, severity, and that it
  happened during the run. *This* file hands that to `exercises.prescription`, and
  `readiness` — untouched — decides what happens to the session.

Nothing here can make a session harder. That guarantee lives in `readiness.apply`,
and this module has no path to it.
"""

from __future__ import annotations

from apps.plans import exercises as exercise_lib

# Salt and heaviness matter in different ways and on different timescales, so they
# are two rules rather than one "heavy meal" rule.
SALT_HIGH = "high"
RICH_HEAVY = "heavy"


def _tone(level: str) -> str:
    return {"warn": "warn", "good": "good"}.get(level, "neutral")


def hydration_notes(analysis: dict) -> list[dict]:
    """Fluid consequences of what they ate and drank.

    Deliberately about the *next* session rather than about diet. This app has no
    business telling anyone what to eat; it has every business pointing out that a
    salty dinner and a hot morning run interact.
    """
    out: list[dict] = []
    meals = analysis.get("meals") or []

    salty = [m for m in meals if m.get("salt") == SALT_HIGH]
    heavy = [m for m in meals if m.get("richness") == RICH_HEAVY]
    hot = [m for m in meals if m.get("spice") == "hot"]
    late = [m for m in meals if m.get("timing") == "late_night"]

    if salty:
        names = ", ".join(m.get("food", "").strip() for m in salty if m.get("food"))
        out.append({
            "tone": "warn",
            "key": "salt",
            "headline": f"Salty meal today — drink more water than usual{f' ({names})' if names else ''}",
            "detail": (
                "A heavily salted meal pulls water out of circulation to dilute the "
                "sodium, so you start tomorrow already down on fluid without feeling "
                "thirsty. An extra 500–750 ml across this evening covers it. This "
                "matters more here than it would in a cooler climate: you are "
                "starting a session in heat, where the margin is already thin."
            ),
        })

    if heavy:
        out.append({
            "tone": "neutral",
            "key": "rich",
            "headline": "Heavy meal — leave it longer before running",
            "detail": (
                "Fat and oil slow the stomach down considerably. If the next session "
                "is within about three hours of eating this, expect it to sit heavily "
                "and either push the run later or keep it easy. It is not a problem "
                "to have eaten it — it is a problem to run 40 minutes after it."
            ),
        })

    if hot:
        out.append({
            "tone": "neutral",
            "key": "spice",
            "headline": "Spicy food before a run day",
            "detail": (
                "Chilli speeds the gut up and can be uncomfortable at running "
                "intensity, particularly in heat. Worth knowing if tomorrow's session "
                "goes badly for reasons that have nothing to do with fitness."
            ),
        })

    if late:
        out.append({
            "tone": "neutral",
            "key": "late_meal",
            "headline": "Late meal — it will show in your sleep data",
            "detail": (
                "Eating close to bed reliably lowers deep sleep and raises overnight "
                "heart rate. Your watch will record it as a poor night, and the "
                "readiness score will follow — worth knowing the cause before reading "
                "it as fatigue."
            ),
        })

    if analysis.get("caffeine_late"):
        out.append({
            "tone": "warn",
            "key": "caffeine",
            "headline": "Caffeine in the evening",
            "detail": (
                "Caffeine has a half-life of five to six hours, so an evening coffee "
                "is still half-present at bedtime. Given sleep debt is currently the "
                "loudest signal in your data, this is the cheapest thing on the list "
                "to fix."
            ),
        })

    note = analysis.get("hydration_note")
    if note:
        out.append({
            "tone": "warn",
            "key": "self_reported",
            "headline": "You mentioned hydration yourself",
            "detail": (
                f"“{note.strip()}” — taken at face value. Thirst lags actual fluid "
                "loss by a long way, so by the time you notice it you are already "
                "meaningfully down."
            ),
        })

    return out


def pain_prescriptions(analysis: dict) -> list[dict]:
    """One exercise prescription per reported niggle, worst first.

    The list is ordered by severity because an athlete reading this has a limited
    budget of attention and the worst thing should spend it.
    """
    entries = analysis.get("pain") or []
    ordered = sorted(entries, key=lambda p: -(p.get("severity") or 0))
    out = []
    for entry in ordered:
        area = entry.get("area")
        if not area:
            continue
        prescription = exercise_lib.prescription(
            area,
            severity=entry.get("severity") or 2,
            when=entry.get("when") or "unclear",
        )
        prescription["quote"] = entry.get("quote", "")
        prescription["side"] = entry.get("side", "unspecified")
        out.append(prescription)
    return out


def build(analysis: dict) -> dict:
    """Everything derived from one analysed entry.

    Returns empty structures rather than nothing when the analysis is missing, so
    the caller never has to special-case an unanalysed log.
    """
    if not analysis:
        return {"hydration": [], "pain": [], "flags": []}

    flags: list[dict] = []

    if analysis.get("illness"):
        flags.append({
            "tone": "warn",
            "key": "illness",
            "headline": "You logged feeling unwell",
            "detail": (
                "Training on top of an infection is how a lost week becomes a lost "
                "month. The session has been dropped rather than shortened — that is "
                "the plan working, not a setback."
            ),
        })

    if analysis.get("stressed"):
        flags.append({
            "tone": "neutral",
            "key": "stress",
            "headline": "A stressful day",
            "detail": (
                "Psychological stress raises resting heart rate and lowers heart-rate "
                "variability the same way physical load does, and your watch cannot "
                "tell the two apart. If tomorrow's readiness looks poor, this is "
                "probably why."
            ),
        })

    if analysis.get("travel"):
        flags.append({
            "tone": "neutral",
            "key": "travel",
            "headline": "Travel logged",
            "detail": (
                "Long journeys mean hours of stillness, poor fluid intake, and dry "
                "air. Drink more than feels necessary and treat the next session as "
                "optional rather than owed."
            ),
        })

    unparsed = analysis.get("unparsed") or []
    if unparsed:
        flags.append({
            "tone": "neutral",
            "key": "unparsed",
            "headline": "Read but not used",
            "detail": (
                "These parts of your entry were understood but do not map to anything "
                "the plan acts on: " + "; ".join(unparsed) + ". They are kept with the "
                "entry in case a later rule needs them."
            ),
        })

    return {
        "hydration": hydration_notes(analysis),
        "pain": pain_prescriptions(analysis),
        "flags": flags,
    }
