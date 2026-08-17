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


def _pace(seconds: Optional[float]) -> str:
    if not seconds:
        return "—"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}/km"


def build(athlete, last_activity, recent_metrics: list, log_count: int, session) -> list[Insight]:
    """recent_metrics: ActivityMetrics ordered newest first."""
    out: list[Insight] = []

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

    return out
