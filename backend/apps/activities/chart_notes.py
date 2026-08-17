"""Per-chart interpretation for the activity detail page.

Each chart gets a short read: what is good, what to change, and how it compares to
the previous session. Computed here rather than in the frontend so the comparison
can reach the database, and so the wording is testable.

Same discipline as the dashboard insights — every claim cites a number this system
actually holds, and where there is no previous session to compare against, the note
says so instead of implying a trend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# A pace change smaller than this is inside GPS noise and is not reported as a trend.
PACE_NOISE_S = 10
# Heart-rate drift within one run block, above which the block was unsustainable.
HR_DRIFT_BPM = 20


@dataclass
class Note:
    tone: str  # "good" | "warn" | "neutral"
    text: str


def _pace(seconds: Optional[float]) -> str:
    if not seconds:
        return "—"
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}/km"


def _mins(seconds: Optional[float]) -> str:
    if not seconds:
        return "0 min"
    return f"{seconds / 60:.1f} min"


# Heart rate takes roughly this long to reach steady state at the start of a run
# block. Drift measured from second zero would count that normal rest-to-work ramp
# as drift and overstate it badly — on a beginner's first block that is a 45 bpm
# difference between the two methods.
HR_RAMP_S = 90
# Comparison windows at each end of the steady-state portion.
DRIFT_WINDOW_S = 20


def _steady_state_drift(activity, segment) -> Optional[int]:
    """Heart-rate drift across a run block, excluding the initial ramp.

    Returns None when the block is too short for the measurement to mean anything.
    """
    import statistics

    usable = segment.duration_s - HR_RAMP_S
    if usable < 2 * DRIFT_WINDOW_S:
        return None

    start = segment.start_offset_s + HR_RAMP_S
    end = segment.start_offset_s + segment.duration_s
    records = list(
        activity.records.filter(offset_s__gte=start, offset_s__lte=end)
        .exclude(heart_rate__isnull=True)
        .values_list("offset_s", "heart_rate")
    )
    if len(records) < 10:
        return None

    early = [hr for offset, hr in records if offset <= start + DRIFT_WINDOW_S]
    late = [hr for offset, hr in records if offset >= end - DRIFT_WINDOW_S]
    if not early or not late:
        return None
    return int(statistics.median(late) - statistics.median(early))


def _emit(notes: dict) -> dict[str, list[dict]]:
    return {k: [{"tone": n.tone, "text": n.text} for n in v] for k, v in notes.items()}


def _non_running_notes(activity, athlete, metrics, walks, notes) -> dict[str, list[dict]]:
    """Read a session with no running in it — a walk, a ride, a gym session."""
    moving = metrics.walk_time_s + metrics.stop_time_s
    label = "walk" if walks else activity.sport.replace("_", " ")

    notes["shape"].append(Note(
        "neutral",
        f"No running detected in this {label}. On this plan that is fine — walking and "
        "cross-training build the aerobic base without the impact load that injures new "
        "runners. It simply is not measured against your run targets.",
    ))

    if moving > 0:
        notes["shape"].append(Note(
            "good" if moving >= 1800 else "neutral",
            f"{_mins(moving)} on your feet"
            + (f" covering {activity.total_distance_m / 1000:.2f} km. " if activity.total_distance_m else ". ")
            + ("That is a solid aerobic session in its own right."
               if moving >= 1800 else
               "Short sessions still count towards the habit, which is what matters most early on."),
        ))

    if walks:
        paces = [w.avg_pace_s_per_km for w in walks if w.avg_pace_s_per_km]
        if paces:
            fastest = min(paces)
            notes["pace"].append(Note(
                "neutral",
                f"Best walking pace was {_pace(fastest)}. Brisk walking around 9:00–10:00/km "
                "sits close to your easy running band, which is why walk breaks work so "
                "well as recovery rather than as stopping.",
            ))

    if activity.avg_hr:
        if activity.avg_hr <= athlete.hr_easy_max:
            notes["hr"].append(Note(
                "good",
                f"Average heart rate {activity.avg_hr} bpm — inside your easy range. "
                "Exactly what a recovery day should look like.",
            ))
        else:
            notes["hr"].append(Note(
                "neutral",
                f"Average heart rate {activity.avg_hr} bpm, above your easy ceiling of "
                f"{athlete.hr_easy_max}. Brisk, but on a non-running day that is not a problem.",
            ))

    ascent = activity.total_ascent_m
    if ascent and activity.total_distance_m:
        notes["elevation"].append(Note(
            "neutral",
            f"{ascent:.0f} m of climbing over {activity.total_distance_m / 1000:.2f} km.",
        ))

    return _emit(notes)


def build(activity, athlete, previous=None) -> dict[str, list[dict]]:
    """previous: the athlete's activity immediately before this one, or None."""
    metrics = getattr(activity, "metrics", None)
    segments = list(activity.segments.all())
    prev_metrics = getattr(previous, "metrics", None) if previous else None

    notes: dict[str, list[Note]] = {
        "shape": [], "route": [], "pace": [], "hr": [], "cadence": [], "elevation": [],
    }
    if metrics is None:
        return {k: [] for k in notes}

    runs = [s for s in segments if s.kind == "run"]
    walks = [s for s in segments if s.kind == "walk"]

    # Almost every note below reads running data, so a walk or a ride would come back
    # nearly blank. Those sessions get their own read instead of an empty page — they
    # are real training on this plan, just measured differently.
    if not runs:
        return _non_running_notes(activity, athlete, metrics, walks, notes)

    # ---------------- session shape ----------------
    if runs:
        longest = max(runs, key=lambda s: s.duration_s)
        if prev_metrics and prev_metrics.longest_run_s:
            delta = metrics.longest_run_s - prev_metrics.longest_run_s
            if delta > 20:
                notes["shape"].append(Note(
                    "good",
                    f"Your longest unbroken run grew to {_mins(metrics.longest_run_s)}, "
                    f"up {_mins(abs(delta))} on last session. This is the number that "
                    "matters most between now and race day.",
                ))
            elif delta < -20:
                notes["shape"].append(Note(
                    "warn",
                    f"Longest unbroken run fell to {_mins(metrics.longest_run_s)}, down "
                    f"{_mins(abs(delta))} on last session. One session is not a trend, "
                    "but if it repeats, slow the run blocks down rather than shortening them.",
                ))
            else:
                notes["shape"].append(Note(
                    "neutral",
                    f"Longest unbroken run held steady at {_mins(metrics.longest_run_s)}, "
                    "essentially level with last session.",
                ))
        else:
            notes["shape"].append(Note(
                "neutral",
                f"Longest unbroken run was {_mins(metrics.longest_run_s)}. No earlier "
                "session to compare against yet — this becomes your baseline.",
            ))

        # A first block much longer than the rest means the session was front-loaded.
        ordered = sorted(runs, key=lambda s: s.start_offset_s)
        if len(ordered) >= 3:
            rest = ordered[1:]
            mean_rest = sum(s.duration_s for s in rest) / len(rest)
            if ordered[0].duration_s > mean_rest * 2.5:
                notes["shape"].append(Note(
                    "warn",
                    f"Your first block ({_mins(ordered[0].duration_s)}) was far longer than "
                    f"the {len(rest)} that followed (average {_mins(mean_rest)}). That is the "
                    "signature of starting too hard and paying for it — aim for blocks of "
                    "even length instead.",
                ))

    # ---------------- route ----------------
    if runs and walks:
        total = metrics.run_time_s + metrics.walk_time_s
        midpoint = total / 2
        late_walk = sum(s.duration_s for s in walks if s.start_offset_s > midpoint)
        if late_walk > metrics.walk_time_s * 0.65:
            notes["route"].append(Note(
                "warn",
                "Most of the walking happened in the second half of the route. Running "
                "the early sections slower usually spreads the run blocks more evenly "
                "across the whole loop.",
            ))
        else:
            notes["route"].append(Note(
                "neutral",
                "Run and walk sections are spread fairly evenly around the route, which "
                "is what an evenly paced session looks like.",
            ))

    # ---------------- pace ----------------
    if metrics.avg_run_pace_s_per_km:
        band = f"{_pace(athlete.easy_pace_min)}–{_pace(athlete.easy_pace_max)}"
        actual = metrics.avg_run_pace_s_per_km
        if actual < athlete.easy_pace_min:
            gap = athlete.easy_pace_min - actual
            notes["pace"].append(Note(
                "warn",
                f"You averaged {_pace(actual)} against a target band of {band} — about "
                f"{int(gap)} seconds per kilometre too fast. Slowing down is the single "
                "change that lets the run blocks get longer.",
            ))
        elif actual > athlete.easy_pace_max:
            notes["pace"].append(Note(
                "good",
                f"You averaged {_pace(actual)}, at or below the easy band of {band}. "
                "Nothing to fix — easy running is supposed to feel this slow.",
            ))
        else:
            notes["pace"].append(Note(
                "good",
                f"You averaged {_pace(actual)}, right inside the {band} band. This is "
                "exactly what the plan asks for.",
            ))

    if metrics.pace_discipline_pct is not None:
        pct = metrics.pace_discipline_pct
        if prev_metrics and prev_metrics.pace_discipline_pct is not None:
            delta = pct - prev_metrics.pace_discipline_pct
            if delta > 8:
                notes["pace"].append(Note(
                    "good",
                    f"Pace discipline improved to {pct:.0f}% from "
                    f"{prev_metrics.pace_discipline_pct:.0f}% last session — the clearest "
                    "sign you are getting the pacing right.",
                ))
            elif delta < -8:
                notes["pace"].append(Note(
                    "warn",
                    f"Pace discipline slipped to {pct:.0f}% from "
                    f"{prev_metrics.pace_discipline_pct:.0f}% last session.",
                ))

    if prev_metrics and prev_metrics.avg_run_pace_s_per_km and metrics.avg_run_pace_s_per_km:
        delta = metrics.avg_run_pace_s_per_km - prev_metrics.avg_run_pace_s_per_km
        if abs(delta) > PACE_NOISE_S:
            # Slower is the goal on this plan, so the tone is inverted deliberately.
            notes["pace"].append(Note(
                "good" if delta > 0 else "neutral",
                f"You ran {int(abs(delta))} s/km "
                f"{'slower' if delta > 0 else 'faster'} than last session "
                f"({_pace(metrics.avg_run_pace_s_per_km)} vs "
                f"{_pace(prev_metrics.avg_run_pace_s_per_km)})."
                + (" On this plan, slower is progress." if delta > 0 else ""),
            ))

    # ---------------- heart rate ----------------
    if metrics.hr_over_ceiling_pct is not None:
        pct = metrics.hr_over_ceiling_pct
        if pct > 25:
            notes["hr"].append(Note(
                "warn",
                f"{pct:.0f}% of your running time was above {athlete.hr_ceiling} bpm. "
                "Crossing the ceiling is the cue to walk — at this level you are "
                "borrowing from the rest of the session.",
            ))
        elif pct < 5:
            notes["hr"].append(Note(
                "good",
                f"Only {pct:.0f}% of running time was above {athlete.hr_ceiling} bpm. "
                "Effort was controlled throughout.",
            ))

    if metrics.avg_hr_overshoot_bpm is not None and metrics.avg_hr_overshoot_bpm > 4:
        notes["hr"].append(Note(
            "warn",
            f"Heart rate kept rising about {metrics.avg_hr_overshoot_bpm:.0f} bpm after you "
            "stopped running. That means the block exceeded what your aerobic system "
            "could cover — it should fall towards zero as fitness comes.",
        ))

    if metrics.avg_hr_recovery_60s is not None:
        value = metrics.avg_hr_recovery_60s
        if prev_metrics and prev_metrics.avg_hr_recovery_60s is not None:
            delta = value - prev_metrics.avg_hr_recovery_60s
            if delta > 3:
                notes["hr"].append(Note(
                    "good",
                    f"Heart-rate recovery improved to {value:.0f} bpm from "
                    f"{prev_metrics.avg_hr_recovery_60s:.0f} last session. This is the "
                    "earliest measurable sign that base fitness is building.",
                ))
        else:
            notes["hr"].append(Note(
                "neutral",
                f"Heart rate dropped {value:.0f} bpm in the first minute of your walk "
                "breaks. Track this — it should climb over the coming weeks.",
            ))

    # Drift inside the longest block says whether the effort was sustainable.
    if runs:
        longest = max(runs, key=lambda s: s.duration_s)
        drift = _steady_state_drift(activity, longest)
        if drift is not None and drift > HR_DRIFT_BPM:
            notes["hr"].append(Note(
                "warn",
                f"Across your longest block, heart rate drifted up {drift} bpm after it had "
                "settled, at a steady pace. A sustainable effort holds roughly level — a "
                "climb like this means the pace was above what you could hold.",
            ))
        elif drift is not None:
            notes["hr"].append(Note(
                "good",
                f"Once heart rate settled, it only drifted {drift} bpm across your longest "
                "block. That part of the effort was sustainable.",
            ))

    # ---------------- cadence ----------------
    if metrics.avg_run_cadence_spm:
        cadence = metrics.avg_run_cadence_spm
        if cadence >= 160:
            notes["cadence"].append(Note(
                "good",
                f"{cadence:.0f} steps per minute while running is already where it should "
                "be. Nothing to change in your form — and it means you can slow down by "
                "shortening your stride rather than slowing your legs.",
            ))
        else:
            notes["cadence"].append(Note(
                "warn",
                f"{cadence:.0f} steps per minute is below the ~170 that keeps impact low. "
                "Try quicker, shorter steps at the same pace.",
            ))

        spread = [s.avg_cadence_spm for s in runs if s.avg_cadence_spm]
        if len(spread) >= 3 and (max(spread) - min(spread)) > 25:
            notes["cadence"].append(Note(
                "warn",
                f"Cadence varied a lot between blocks ({min(spread):.0f}–{max(spread):.0f} "
                "spm), which usually means effort was uneven across the session.",
            ))
        elif len(spread) >= 3:
            notes["cadence"].append(Note(
                "good",
                f"Cadence stayed consistent across all {len(spread)} run blocks "
                f"({min(spread):.0f}–{max(spread):.0f} spm).",
            ))

    # ---------------- conditions ----------------
    # A hot day must not be filed as lost fitness — that is exactly the misreading
    # this note exists to prevent.
    if activity.feels_like_c is not None:
        from apps.ingest.weather import heat_penalty_s_per_km

        penalty = heat_penalty_s_per_km(activity.feels_like_c)
        if penalty:
            notes["pace"].append(Note(
                "neutral",
                f"It felt like {activity.feels_like_c:.0f} °C"
                + (f" at {activity.humidity_pct:.0f}% humidity" if activity.humidity_pct else "")
                + f". Heat alone costs roughly {penalty} s/km at the same effort, so judge "
                "this session by heart rate rather than pace.",
            ))

    # ---------------- elevation ----------------
    ascent = activity.total_ascent_m
    if ascent is not None and activity.total_distance_m:
        per_km = ascent / (activity.total_distance_m / 1000)
        if per_km < 12:
            notes["elevation"].append(Note(
                "neutral",
                f"{ascent:.0f} m of climbing over {activity.total_distance_m / 1000:.2f} km "
                "is essentially flat, so the terrain does not explain the pace either way.",
            ))
        else:
            notes["elevation"].append(Note(
                "neutral",
                f"{ascent:.0f} m of climbing ({per_km:.0f} m per km). Expect pace to be "
                "slower than on flat ground — judge this session by heart rate rather "
                "than pace.",
            ))

    return _emit(notes)
