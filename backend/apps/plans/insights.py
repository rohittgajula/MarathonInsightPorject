"""Plain-language read on where the athlete stands.

Every statement here is tied to a number the system actually holds. Where there is
not enough data to support a claim, it says so rather than inventing confidence —
with three runs a week, most "X causes Y" conclusions are noise until well into the
plan, and a training tool that overstates early is one you stop trusting by month three.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

# Below this many observations a comparison is reported as provisional, and below
# MIN_FOR_ANY_CLAIM it is not reported as a finding at all.
MIN_FOR_ANY_CLAIM = 12
MIN_FOR_CONFIDENT_CLAIM = 20


@dataclass
class Insight:
    tone: str  # "good" | "warn" | "neutral"
    headline: str
    detail: str


# A resting heart rate this far above the recent baseline is the classic early
# warning for fatigue or illness — usually a day or two before it is felt.
RHR_RISE_BPM = 4
# Nights of sleep debt in a week before it is worth naming.
SLEEP_DEBT_H = 6.0


def _recovery_cards(wellness: list, today) -> list[Insight]:
    """Cards driven by the watch, which refresh with every daily sync."""
    if not wellness:
        return []

    out: list[Insight] = []
    latest = wellness[-1]
    week = wellness[-7:]

    readiness = latest.get("training_readiness")
    if readiness is not None:
        if readiness < 20:
            out.append(Insight(
                "warn", f"Training readiness {readiness}/100 today",
                "Your watch is saying today is not a day to train. Walk if you want to "
                "move, but the session can wait — this is the number the plan defers to.",
            ))
        elif readiness < 40:
            out.append(Insight(
                "warn", f"Training readiness {readiness}/100 today",
                "Low. Take the easy end of the pace range and stop if it feels harder "
                "than usual.",
            ))
        elif readiness >= 65:
            out.append(Insight(
                "good", f"Training readiness {readiness}/100 today",
                "A good day to do the session as written.",
            ))

    debts = [w.get("sleep_deficit_hours") for w in week
             if w.get("sleep_deficit_hours") is not None]
    total_debt = sum(d for d in debts if d > 0)
    if total_debt >= SLEEP_DEBT_H:
        nights = sum(1 for d in debts if d > 0)
        out.append(Insight(
            "warn", f"{total_debt:.0f} hours of sleep debt this week",
            f"Short on {nights} of the last {len(debts)} nights. At your stage the "
            "aerobic adaptations you are training for are consolidated during sleep, "
            "so this blunts the work rather than just making you tired.",
        ))

    rhrs = [w.get("resting_hr") for w in wellness if w.get("resting_hr")]
    if len(rhrs) >= 7:
        recent = rhrs[-3:]
        baseline = rhrs[-14:-3] or rhrs[:-3]
        if baseline:
            delta = sum(recent) / len(recent) - sum(baseline) / len(baseline)
            if delta >= RHR_RISE_BPM:
                out.append(Insight(
                    "warn", f"Resting heart rate up {delta:.0f} bpm on your baseline",
                    "A sustained rise usually shows up a day or two before you feel "
                    "run down. Worth easing off until it settles.",
                ))
            elif delta <= -RHR_RISE_BPM:
                out.append(Insight(
                    "good", f"Resting heart rate down {abs(delta):.0f} bpm",
                    "A falling resting heart rate is one of the clearest signs aerobic "
                    "fitness is improving.",
                ))
    return out


def _pace(seconds: Optional[float]) -> str:
    if not seconds:
        return "—"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}/km"


def build(athlete, last_activity, recent_metrics: list, log_count: int, session,
          wellness: list | None = None, today=None) -> list[Insight]:
    """recent_metrics: ActivityMetrics ordered newest first.

    wellness is ordered oldest first. Activity-derived cards only change when a new
    run lands, which on three runs a week means the panel can sit unchanged for days.
    The recovery cards below move every morning, which is both more useful and a
    truer picture of what is actually different today.
    """
    out: list[Insight] = []
    out.extend(_recovery_cards(wellness or [], today))

    if last_activity is None:
        out.append(Insight(
            "neutral", "No runs recorded yet",
            "Upload a .fit file, or connect Garmin, and this fills in with your own numbers.",
        ))
        return out

    latest = recent_metrics[0] if recent_metrics else None

    if latest and latest.pace_discipline_pct is not None:
        band = f"{_pace(athlete.easy_pace_min)}–{_pace(athlete.easy_pace_max)}"
        if latest.pace_discipline_pct < 25:
            out.append(Insight(
                "warn",
                f"You ran {latest.pace_discipline_pct:.0f}% of last session in your easy band",
                f"Your target is {band}; you averaged {_pace(latest.avg_run_pace_s_per_km)}. "
                "Running slower is the single change that lets the run blocks get longer. "
                "Keep your cadence and shorten your stride.",
            ))
        elif latest.pace_discipline_pct >= 60:
            out.append(Insight(
                "good",
                f"Pace discipline {latest.pace_discipline_pct:.0f}%",
                f"Most of your running sat inside {band}. This is what makes the "
                "next distance step possible.",
            ))

    if latest and latest.avg_hr_overshoot_bpm is not None and latest.avg_hr_overshoot_bpm > 4:
        out.append(Insight(
            "warn",
            f"Heart rate kept climbing {latest.avg_hr_overshoot_bpm:.0f} bpm after you stopped",
            "That means the run block was above what your aerobic system could cover. "
            "It is the clearest sign to slow the run blocks down rather than shorten them.",
        ))

    # Longest continuous run is the number that actually predicts finishing a 10K.
    longest = [m.longest_run_s for m in recent_metrics if m.longest_run_s]
    if len(longest) >= 3:
        best_recent = max(longest[:3])
        best_before = max(longest[3:]) if len(longest) > 3 else None
        if best_before and best_recent > best_before * 1.15:
            out.append(Insight(
                "good", "Your longest unbroken run is growing",
                f"Best of your last three sessions is {best_recent / 60:.1f} min, up from "
                f"{best_before / 60:.1f} min before that.",
            ))

    recoveries = [m.avg_hr_recovery_60s for m in recent_metrics if m.avg_hr_recovery_60s is not None]
    if len(recoveries) >= MIN_FOR_ANY_CLAIM:
        first_half = recoveries[: len(recoveries) // 2]
        second_half = recoveries[len(recoveries) // 2 :]
        delta = sum(first_half) / len(first_half) - sum(second_half) / len(second_half)
        confident = len(recoveries) >= MIN_FOR_CONFIDENT_CLAIM
        if delta > 3:
            out.append(Insight(
                "good", "Heart-rate recovery is improving",
                f"Recovery in your walk breaks is {delta:.0f} bpm better than earlier in the plan."
                + ("" if confident else " Based on limited data — treat as provisional."),
            ))
    elif recoveries:
        out.append(Insight(
            "neutral", "Heart-rate recovery: building a baseline",
            f"{len(recoveries)} of {MIN_FOR_ANY_CLAIM} sessions needed before a trend "
            "means anything. Recovery in walk breaks is the clearest early sign fitness is coming.",
        ))

    if latest and latest.avg_run_cadence_spm:
        cadence = latest.avg_run_cadence_spm
        if cadence >= 160:
            out.append(Insight(
                "good", f"Cadence {cadence:.0f} steps per minute",
                "This is already where it should be, so there is nothing to fix in your "
                "form. It also means you can slow down by shortening your stride rather "
                "than by slowing your legs — same rhythm, smaller steps.",
            ))
        elif cadence < 150:
            out.append(Insight(
                "warn", f"Cadence {cadence:.0f} steps per minute is low",
                "Under about 160 usually means overstriding, which lands you heavily and "
                "raises injury risk. Try quicker, smaller steps at the same pace.",
            ))

    # Walking is not failure on this plan, but the ratio says what the session was.
    if latest and latest.run_time_s and latest.walk_time_s:
        run_share = 100 * latest.run_time_s / (latest.run_time_s + latest.walk_time_s)
        out.append(Insight(
            "neutral", f"You ran {run_share:.0f}% of your moving time",
            f"{latest.run_time_s / 60:.0f} min running against "
            f"{latest.walk_time_s / 60:.0f} min walking, across {latest.run_block_count} "
            "blocks. Walk breaks are part of the plan — the number to watch is whether "
            "the run blocks get longer, not whether the walking disappears.",
        ))

    # Consistency beats any single session, so it gets its own card.
    if len(recent_metrics) >= 2:
        recent_dates = [m.activity.local_date for m in recent_metrics[:6] if m.activity_id]
        if len(recent_dates) >= 2:
            span = (recent_dates[0] - recent_dates[-1]).days or 1
            per_week = len(recent_dates) / (span / 7) if span >= 7 else None
            if per_week is not None:
                if per_week < 2:
                    out.append(Insight(
                        "warn", f"About {per_week:.1f} runs a week",
                        "The plan assumes three. Two is enough to hold fitness but not "
                        "enough to build it — consistency matters more here than any "
                        "single session.",
                    ))
                elif per_week >= 2.5:
                    out.append(Insight(
                        "good", f"About {per_week:.1f} runs a week",
                        "On track with the plan's three sessions. This is the single "
                        "strongest predictor of arriving at the start line ready.",
                    ))

    if log_count < MIN_FOR_ANY_CLAIM:
        out.append(Insight(
            "neutral", "Not enough daily logs to correlate anything yet",
            f"{log_count} of {MIN_FOR_ANY_CLAIM} entries. Sleep and alcohol effects are "
            "indistinguishable from noise until then, so nothing is claimed about them.",
        ))

    if session and session.kind != "rest":
        out.append(Insight(
            "neutral", f"Tomorrow: {session.title}",
            session.detail,
        ))
    elif session:
        out.append(Insight(
            "neutral", "Tomorrow is a rest day",
            "No running. Adaptation happens on the days you don't run, so this is part "
            "of the training rather than a gap in it.",
        ))

    return out
