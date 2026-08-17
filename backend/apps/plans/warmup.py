"""Pre-run activation routine.

Deliberately a *dynamic* warm-up, not static stretching. Static stretching before
running has repeatedly failed to reduce injury rates and temporarily reduces force
output; brief dynamic activation of the specific muscles that stabilise the knee and
ankle is the part with support behind it.

The selection targets the two things that actually injure new runners: hip abductor
weakness (which lets the knee collapse inward under load) and calf/achilles capacity
(which absorbs most of the impact when cadence is high and stride is short, as here).

`muscles` maps onto the highlight regions in the frontend body diagram.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Exercise:
    key: str
    name: str
    duration: str
    muscles: list[str]
    primary: str
    why: str
    how: str


ROUTINE: list[Exercise] = [
    Exercise(
        key="ankle_circles",
        name="Ankle circles",
        duration="20 s each foot",
        muscles=["calf", "shin"],
        primary="Ankle joint",
        why=(
            "The ankle takes the first impact of every stride. Loosening it before you "
            "load it reduces the shock passed up to the shin, which is where most "
            "beginner niggles start."
        ),
        how=(
            "Stand on one leg, lift the other foot slightly and draw slow circles with "
            "your toes. Ten each direction, then swap."
        ),
    ),
    Exercise(
        key="leg_swings",
        name="Forward leg swings",
        duration="12 each leg",
        muscles=["hamstring", "hip_flexor", "glute"],
        primary="Hips and hamstrings",
        why=(
            "Opens the hip through the range running actually uses. Tight hip flexors "
            "shorten your stride and push you to reach with the foot instead, which "
            "lands you heel-first ahead of your body."
        ),
        how=(
            "Hold a wall for balance. Swing one leg forward and back, relaxed and "
            "controlled, letting the range grow as it loosens. Do not force it."
        ),
    ),
    Exercise(
        key="lateral_swings",
        name="Side-to-side leg swings",
        duration="12 each leg",
        muscles=["glute", "adductor", "hip_flexor"],
        primary="Glutes and adductors",
        why=(
            "Wakes up the muscles that stop your knee drifting inward. That inward "
            "collapse is the single most common cause of runner's knee."
        ),
        how="Face the wall, swing one leg across your body and back out. Keep hips square.",
    ),
    Exercise(
        key="glute_bridge",
        name="Glute bridges",
        duration="12 reps",
        muscles=["glute", "hamstring", "core"],
        primary="Glutes",
        why=(
            "Most people who sit all day run with underactive glutes, which hands the "
            "work to the hamstrings and lower back. Two minutes here changes which "
            "muscles drive the stride."
        ),
        how=(
            "Lie on your back, knees bent, feet flat. Push through your heels to lift "
            "your hips until shoulder-knee is a straight line. Squeeze at the top, lower slowly."
        ),
    ),
    Exercise(
        key="calf_raises",
        name="Calf raises",
        duration="15 reps",
        muscles=["calf"],
        primary="Calves and achilles",
        why=(
            "Your cadence is high and your stride short, which is correct — and it "
            "means the calves absorb more of each step. Loading them briefly first "
            "prepares the achilles for that."
        ),
        how=(
            "Stand tall, rise onto your toes slowly, hold for a second at the top, "
            "lower under control. Slower is better than higher."
        ),
    ),
    Exercise(
        key="walk_in",
        name="Brisk walk",
        duration="5 min",
        muscles=["calf", "glute", "hamstring", "quad"],
        primary="Whole body",
        why=(
            "Raises heart rate gradually so the first run block does not start with a "
            "spike. On your 17 August run, heart rate climbed from 110 to 158 inside "
            "the first block — walking in first flattens that ramp."
        ),
        how="Walk at a pace where you could still talk comfortably, straight into the session.",
    ),
]

# Regions the frontend body diagram can highlight.
MUSCLE_LABELS = {
    "calf": "Calves",
    "shin": "Shins",
    "hamstring": "Hamstrings",
    "quad": "Quads",
    "glute": "Glutes",
    "hip_flexor": "Hip flexors",
    "adductor": "Inner thigh",
    "core": "Core",
}


def routine() -> dict:
    total = "About 8 minutes"
    return {
        "total": total,
        "intro": (
            "Do this before every run. It is dynamic activation, not stretching — "
            "static stretching before running has not been shown to prevent injury "
            "and temporarily reduces force output."
        ),
        "muscle_labels": MUSCLE_LABELS,
        "exercises": [asdict(e) for e in ROUTINE],
    }
