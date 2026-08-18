"""Turn a prescribed session into something a new runner can actually execute.

The plan says "8 × (1 min run / 2 min walk)". That is a specification, not
instructions. This expands it into the concrete things someone standing at their
front door needs: the exact sequence, what heart rate to hold, what to do when it
goes wrong, and how to run in the first place.

The form cues are the conservative, well-supported ones — cadence, posture, landing
under the body, relaxed breathing. Deliberately no advice on forefoot versus heel
striking: the evidence does not support prescribing a foot strike, and telling a new
runner to change theirs is a reliable way to produce a calf or achilles injury.
"""

from __future__ import annotations


def _fmt(minutes: float) -> str:
    if minutes == int(minutes):
        return f"{int(minutes)} min"
    whole = int(minutes)
    return f"{whole}:{int(round((minutes - whole) * 60)):02d}"


def steps_for(session, athlete) -> list[dict]:
    """The session as an ordered list of things to do.

    Everything is derived from the session, including whether a warm-up belongs at
    all: prescribing an activation routine and a cool-down around a recovery walk
    adds ceremony to the one day whose whole purpose is doing less.
    """
    if session is None or session.kind == "rest":
        return []

    pace = session.target_pace or ""

    if session.kind == "walk":
        minutes = int(session.total_minutes) if session.total_minutes else 28
        return [{
            "label": "The walk",
            "detail": (
                f"About {minutes} minutes at {pace}, brisk enough that talking takes a "
                "little effort. No warm-up needed and nothing to build up to — the walk "
                "is the session."
                if pace else
                f"About {minutes} minutes brisk walking. The walk is the session — no "
                "warm-up needed."
            ),
            "duration": f"{minutes} min",
        }]

    steps: list[dict] = [{
        "label": "Warm up",
        "detail": "5 minutes brisk walking, plus the activation routine on the Warm-up page.",
        "duration": "5 min",
    }]

    if session.kind == "intervals" and session.run_minutes:
        # Reconstruct the reps from the title the template generated.
        title = session.title.replace(" — shortened", "")
        steps.append({
            "label": "Main set",
            "detail": (
                f"{title}. Run blocks at {pace}. Walk the recoveries properly — "
                "keep moving, do not stand still."
            ),
            "duration": f"{session.run_minutes:g} min running",
        })
    elif session.kind in ("long", "jog") and session.distance_km:
        steps.append({
            "label": "Main set",
            "detail": (
                f"{session.distance_km:g} km run/walk at {pace}. Start the walk breaks "
                "before you need them — the aim is to finish the distance, not to see "
                "how long you can hold out."
            ),
            "duration": f"{session.distance_km:g} km",
        })
    elif session.kind == "race":
        steps.append({
            "label": "The race",
            "detail": (
                "Start at the back. First kilometre 30 s/km slower than training pace. "
                "Hold your run/walk pattern from kilometre one."
            ),
            "duration": f"{session.distance_km:g} km" if session.distance_km else "Race",
        })

    steps.append({
        "label": "Cool down",
        "detail": "5 minutes easy walking until your breathing settles. Do not stop dead.",
        "duration": "5 min",
    })
    return steps


def targets_for(session, athlete, metrics=None) -> list[dict]:
    """The numbers to hold during the session, each with what it means in the body.

    Read from the session rather than from the athlete's defaults. The session is the
    thing that changes — a readiness downgrade turns an interval day into a walk with
    a different pace band, a lower heart-rate range and no run cadence — and pulling
    the numbers from the profile instead meant the card confidently prescribed a
    running heart rate for a walk.
    """
    if session is None or session.kind == "rest":
        return []

    walking = session.kind == "walk"
    out = []

    if session.target_pace:
        out.append({
            "label": "Pace",
            "value": session.target_pace,
            "note": ("Brisk enough that talking takes a little effort, but you are not "
                     "breathing hard." if walking else
                     "Slow enough to speak a full sentence. If you cannot, you are too fast."),
        })

    if session.target_hr:
        out.append({
            "label": "Heart rate",
            "value": session.target_hr,
            "note": ("Comfortably below your running range — this is recovery, and going "
                     "harder defeats the point of the day." if walking else
                     "The range you could hold for an hour. This is the number to obey."),
        })

    if not walking:
        out.append({
            "label": "Walk when above",
            "value": f"{athlete.hr_ceiling} bpm",
            "note": ("Cross this and walk until it drops back under "
                     f"{athlete.hr_easy_min}. Not a failure — it is the plan working."),
        })
        out.append({
            "label": "Cadence",
            "value": f"{max(athlete.run_cadence_threshold + 25, 165)}+ steps/min",
            "note": ("Quick, light steps. Slow down by shortening your stride, never by "
                     "slowing your legs."),
        })
    else:
        out.append({
            "label": "Effort",
            "value": "Conversational",
            "note": ("If you find yourself pushing, ease off. A walk day exists to let "
                     "the last session land, not to add more."),
        })

    if metrics is not None and metrics.get("last_avg_hr") and not walking:
        out.append({
            "label": "Last session average",
            "value": f"{metrics['last_avg_hr']} bpm",
            "note": "What you actually held last time, for comparison.",
        })
    return out


FORM_CUES = [
    {
        "key": "posture",
        "title": "Stand tall, lean from the ankles",
        "cue": "Imagine a string lifting the top of your head. Lean very slightly forward "
               "from the ankles, not the waist.",
        "why": "Bending at the waist closes the hips and shortens the stride, which makes "
               "every step cost more.",
    },
    {
        "key": "landing",
        "title": "Land under your hips, not in front",
        "cue": "Your foot should touch down roughly beneath your body. If you can see your "
               "foot land out in front of you, you are reaching.",
        "why": "Reaching puts the foot ahead of your centre of mass, which brakes you on "
               "every step and drives impact up into the knee. This — not which part of "
               "the foot lands first — is the thing worth fixing.",
    },
    {
        "key": "cadence",
        "title": "Quick, light steps",
        "cue": "Aim for around 170 steps a minute. Count one foot for 15 seconds and "
               "multiply by four — around 42 is right.",
        "why": "You already run at 169. Higher cadence shortens the stride automatically, "
               "which is what keeps you landing underneath yourself.",
    },
    {
        "key": "arms",
        "title": "Relaxed arms, elbows back",
        "cue": "Elbows around 90°, hands loose as if holding a crisp you do not want to "
               "break. Drive the elbow backwards, let it swing forward on its own.",
        "why": "Arms crossing the body twists the torso and wastes energy. Clenched hands "
               "tighten the shoulders and neck.",
    },
    {
        "key": "breathing",
        "title": "Breathe into your belly, through mouth and nose",
        "cue": "Let your stomach rise as you breathe in. Try a rhythm of three steps in, "
               "two steps out — and if you cannot manage it, you are running too fast.",
        "why": "Shallow chest breathing uses only the top of the lungs. Belly breathing "
               "moves more air for the same effort, and the rhythm doubles as a pace check.",
    },
    {
        "key": "relax",
        "title": "Check for tension every few minutes",
        "cue": "Run through it: jaw loose, shoulders down, hands soft. Shake the arms out "
               "if you find tension.",
        "why": "Tension costs energy and does nothing for speed. New runners carry most of "
               "it in the shoulders and jaw without noticing.",
    },
]

TROUBLESHOOTING = [
    {
        "problem": "I get out of breath in the first two minutes",
        "answer": "You started too fast — it is almost always this. Begin slower than feels "
                  "reasonable; the first kilometre should feel like you are holding back.",
    },
    {
        "problem": "A stitch in my side",
        "answer": "Slow to a walk, press gently into the spot and breathe out hard as the "
                  "opposite foot lands. Usually eating too close to running, or shallow "
                  "breathing.",
    },
    {
        "problem": "My shins hurt",
        "answer": "Common when starting out. Shorten your stride, raise your cadence, and "
                  "take an extra rest day. Pain that persists past a warm-up means stop.",
    },
    {
        "problem": "I cannot finish the run blocks",
        "answer": "Slow the run blocks rather than shortening them. If a block still fails "
                  "at a genuinely easy pace, repeat the week rather than pushing on.",
    },
    {
        "problem": "My heart rate is above the ceiling the whole time",
        "answer": "Walk more. On this plan the walk breaks are the training, not a break "
                  "from it. Heart rate settles as base fitness builds, over weeks.",
    },
]
