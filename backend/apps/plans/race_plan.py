"""A concrete plan for race day.

The generic advice ("start slow, walk the aid stations") is right but unusable at
kilometre 6 with a heart rate you did not expect. This turns it into numbers: what
pace to hold, when to walk, what each split should read, and what to do when it goes
wrong.

Everything is derived from the athlete's own data, and the run/walk pattern is the one
they trained with — race day is the worst possible moment to try running continuously
for the first time.
"""

from __future__ import annotations


def _pace(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def build(athlete, race, metrics=None) -> dict:
    distance_km = (race.distance_m or 10000) / 1000

    # Race pace is the easy band's slow edge — deliberately not faster. A first race
    # run at training pace finishes; one run at "race pace" walks the last third.
    target = athlete.easy_pace_max
    opening = target + 30          # first km deliberately slower again
    finish_s = target * distance_km

    splits = []
    for km in range(1, int(distance_km) + 1):
        if km == 1:
            note, pace = "Deliberately slow. The crowd will make this feel too easy — good.", opening
        elif km <= 3:
            note, pace = "Settle in. Hold the walk breaks even though you feel fine.", target
        elif km <= int(distance_km) - 2:
            note, pace = "The working middle. Keep the pattern, take the water.", target
        elif km < int(distance_km):
            note, pace = "It gets hard here. Shorten the stride, keep the cadence.", target
        else:
            note, pace = "Last kilometre. Run it in if you have it, walk it in if you do not.", target
        splits.append({
            "km": km,
            "target_pace": f"{_pace(pace)}/km",
            "cumulative": _pace(sum(
                (opening if k == 1 else target) for k in range(1, km + 1)
            )),
            "note": note,
        })

    return {
        "race_name": race.name,
        "race_date": race.race_date,
        "distance_km": distance_km,
        "goal": "Finish. There is no time target, and chasing one is how first races go wrong.",
        "target_pace": f"{_pace(target)}/km",
        "opening_pace": f"{_pace(opening)}/km",
        "estimated_finish": f"{int(finish_s // 60)}–{int(finish_s // 60) + 12} min",
        "hr_ceiling": athlete.hr_ceiling,
        "splits": splits,
        "walk_plan": {
            "pattern": "Walk 60 seconds at every kilometre marker, from kilometre one.",
            "why": (
                "Taking breaks before you need them is what makes the last 3 km "
                "possible. Waiting until you are forced to walk means walking far more "
                "in total — which is exactly what happened on 17 August."
            ),
        },
        "before": [
            {"when": "Night before", "do": "Normal food, nothing new. Lay everything out. "
                                           "Poor sleep the night before a race costs almost nothing — "
                                           "the sleep two nights before is the one that matters."},
            {"when": "3 hours before", "do": "Something familiar you have eaten before a run. "
                                             "Race morning is not the day to try porridge for the first time."},
            {"when": "60 minutes before", "do": "Stop drinking large amounts. Sip only."},
            {"when": "20 minutes before", "do": "The warm-up routine. Do not skip it because "
                                                "you are nervous — that is when it matters most."},
            {"when": "In the pen", "do": "Start at the back. Every place you gain at the start "
                                         "is one you pay for at kilometre 7."},
        ],
        "if_it_goes_wrong": [
            {"problem": "Heart rate above your ceiling early",
             "answer": f"Walk until it is back under {athlete.hr_easy_min}. Losing 60 seconds "
                       "at kilometre 2 is nothing; blowing up at kilometre 6 costs ten minutes."},
            {"problem": "You feel great at halfway",
             "answer": "Do not speed up. Everyone feels good at halfway. Hold the pattern and "
                       "spend it in the last two kilometres if it is still there."},
            {"problem": "A stitch",
             "answer": "Walk, press into it, breathe out hard as the opposite foot lands."},
            {"problem": "You want to stop",
             "answer": "Walk instead of stopping. Walking still finishes; stopping rarely restarts."},
        ],
    }
