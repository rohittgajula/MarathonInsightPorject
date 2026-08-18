"""Strength, mobility and rehab work for runners, indexed by what hurts.

`warmup.py` answers "what do I do in the ten minutes before a run". This answers the
other two questions: what do I do about the thing that is sore, and what do I do
twice a week so it does not come back.

The catalogue is deliberately conservative about its own authority. Everything here
is load management and general conditioning — the exercises a physiotherapist would
start with, at doses a beginner can actually absorb. Nothing here diagnoses. Where a
presentation needs a person rather than an app (night pain, swelling, a limp, pain
that does not settle in two weeks), the prescription says so and says it first.

Doses are per-session and assume the athlete is not currently in acute pain unless
the exercise is tagged `acute`. Progression is by adding reps before adding load,
because tendon and bone adapt several weeks slower than the muscle around them —
which is the single fact that explains most beginner running injuries.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Kinds of work, ordered by how a session should be assembled from them.
MOBILITY = "mobility"
ACTIVATION = "activation"
STRENGTH = "strength"
REHAB = "rehab"
DRILL = "drill"
CORE = "core"

KIND_LABELS = {
    MOBILITY: "Mobility",
    ACTIVATION: "Activation",
    STRENGTH: "Strength",
    REHAB: "Rehab",
    DRILL: "Running drill",
    CORE: "Core",
}


@dataclass
class Exercise:
    key: str
    name: str
    kind: str
    # Body areas this addresses. Matches the pain areas the log extractor reports and
    # the highlight regions in the frontend body diagram.
    areas: list[str]
    dose: str
    why: str
    how: str
    # Muscles for the body diagram; may be broader than `areas`, because the fix for
    # a sore knee is usually not at the knee.
    muscles: list[str] = field(default_factory=list)
    # True when it is safe and useful while the area is still sore. Everything else
    # waits until pain has settled.
    acute: bool = False
    caution: str = ""


CATALOGUE: list[Exercise] = [
    # ---------------------------------------------------------------- foot & arch
    Exercise(
        key="towel_scrunch", name="Towel scrunches", kind=REHAB,
        areas=["foot"], muscles=["foot"], acute=True,
        dose="3 × 15 each foot",
        why=(
            "The small muscles inside the arch are what hold it up under load. When "
            "they fatigue the arch flattens further with each kilometre, which is why "
            "foot pain so often arrives late in a run rather than at the start."
        ),
        how=(
            "Sit with a towel flat under one bare foot. Keeping the heel down, scrunch "
            "the towel toward you using only your toes. Slow — this is not a speed drill."
        ),
    ),
    Exercise(
        key="arch_doming", name="Short foot (arch doming)", kind=REHAB,
        areas=["foot"], muscles=["foot"], acute=True,
        dose="3 × 10 holds of 5 s, each foot",
        why=(
            "Trains the arch to lift without curling the toes — the exact action it "
            "has to perform mid-stance. It is the most specific thing you can do for "
            "an arch that aches under load."
        ),
        how=(
            "Barefoot, foot flat. Without gripping with your toes, draw the ball of "
            "the foot slightly toward the heel so the arch lifts. Hold 5 s, release."
        ),
    ),
    Exercise(
        key="plantar_roll", name="Arch roll", kind=MOBILITY,
        areas=["foot"], muscles=["foot"], acute=True,
        dose="2 min each foot",
        why=(
            "Desensitises the sole and gets blood into tissue with a famously poor "
            "supply. Most useful first thing in the morning, when plantar pain is worst."
        ),
        how=(
            "Roll the sole slowly over a ball or a frozen water bottle, heel to toes. "
            "Firm pressure, never sharp pain."
        ),
    ),
    Exercise(
        key="toe_yoga", name="Toe splay and lift", kind=ACTIVATION,
        areas=["foot"], muscles=["foot"], acute=True,
        dose="2 × 10 each foot",
        why=(
            "Restores independent control of the big toe, which is what pushes you "
            "off the ground. Shoes take this away from almost everyone."
        ),
        how=(
            "Foot flat. Lift only the big toe, keeping the others down. Then reverse: "
            "big toe down, others up. Slow and deliberate — it will feel impossible at first."
        ),
    ),

    # ------------------------------------------------------------ calf & achilles
    Exercise(
        key="calf_raise_double", name="Double-leg calf raise", kind=STRENGTH,
        areas=["calf", "achilles", "foot"], muscles=["calf"], acute=True,
        dose="3 × 15, slow down over 3 s",
        why=(
            "The calf and achilles absorb the largest single share of the impact in "
            "running. Load capacity here is the strongest protection a beginner has, "
            "and the slow lowering is the part the tendon responds to."
        ),
        how=(
            "Stand with the balls of your feet on a step, heels hanging. Rise up on "
            "both feet, then take a full 3 s to lower below the step."
        ),
    ),
    Exercise(
        key="calf_raise_single", name="Single-leg calf raise", kind=STRENGTH,
        areas=["calf", "achilles", "ankle"], muscles=["calf"],
        dose="3 × 12 each leg",
        why=(
            "Running is a series of single-leg landings, so single-leg capacity is "
            "what actually matters. Being able to do 20 clean reps a side is a "
            "reasonable target before distance climbs much further."
        ),
        how="As the double-leg version, one foot at a time. Fingertips on a wall for balance only.",
        caution="Progress to this only once the double-leg version is painless.",
    ),
    Exercise(
        key="bent_knee_calf", name="Bent-knee calf raise", kind=STRENGTH,
        areas=["achilles", "calf"], muscles=["calf"],
        dose="3 × 12 each leg",
        why=(
            "Bending the knee shifts the work from the big calf muscle to the soleus "
            "underneath it — the one that takes most of the load at easy running "
            "paces, and the one most often missed."
        ),
        how="Calf raise with the knee bent to about 20°. Keep the bend constant throughout.",
    ),
    Exercise(
        key="ankle_alphabet", name="Ankle alphabet", kind=MOBILITY,
        areas=["ankle", "achilles"], muscles=["shin", "calf"], acute=True,
        dose="One alphabet each foot",
        why="Moves the ankle through its full range in every direction without loading it.",
        how="Sitting, foot off the floor, draw each letter of the alphabet with your big toe.",
    ),
    Exercise(
        key="knee_to_wall", name="Knee-to-wall ankle mobility", kind=MOBILITY,
        areas=["ankle", "calf", "achilles", "knee"], muscles=["calf", "shin"], acute=True,
        dose="2 × 10 each side",
        why=(
            "A stiff ankle cannot let the shin travel forward over the foot, so the "
            "load has to go somewhere else — usually the knee or the arch. This is "
            "one of the most common hidden causes of pain elsewhere."
        ),
        how=(
            "Face a wall, toes about 10 cm back. Drive the knee forward to touch the "
            "wall without the heel lifting. Move the foot back as it improves."
        ),
    ),

    # -------------------------------------------------------------------- shin
    Exercise(
        key="heel_walk", name="Heel walks", kind=STRENGTH,
        areas=["shin"], muscles=["shin"], acute=True,
        dose="3 × 30 s",
        why=(
            "Shin splints are usually the front of the shin failing to control the "
            "foot's drop after landing. Strengthening it directly is the fix; "
            "stretching the calf alone is not."
        ),
        how="Walk on your heels with toes lifted as high as you can hold them.",
    ),
    Exercise(
        key="toe_raise", name="Seated toe raises", kind=REHAB,
        areas=["shin"], muscles=["shin"], acute=True,
        dose="3 × 20",
        why="The same muscle as heel walks, loaded gently enough to use while the shin is still sore.",
        how="Sit with feet flat. Lift the toes and forefoot as high as possible, keeping heels down. Lower slowly.",
    ),

    # -------------------------------------------------------------------- knee
    Exercise(
        key="step_down", name="Slow step-downs", kind=REHAB,
        areas=["knee", "quad", "hip"], muscles=["quad", "glute"],
        dose="3 × 8 each leg",
        why=(
            "Runner's knee is usually a control problem, not a damage problem: the "
            "knee drifts inward under load. This trains exactly the moment that "
            "happens, at a speed where you can correct it."
        ),
        how=(
            "Stand on one leg on a low step. Take 3 s to lower the other heel toward "
            "the floor, tap, and come back up. Watch the standing knee stays over the "
            "middle of the foot, not inside it."
        ),
        caution="Reduce the step height until it is painless. Height is the dose here.",
    ),
    Exercise(
        key="wall_sit", name="Wall sit", kind=STRENGTH,
        areas=["knee", "quad"], muscles=["quad"], acute=True,
        dose="3 × 30–45 s",
        why=(
            "Loads the quad hard with no movement at the knee, so it builds the "
            "support the joint needs while it is still too sore for step-downs."
        ),
        how="Back flat against a wall, slide down to about 60° at the knee, hold.",
    ),
    Exercise(
        key="terminal_knee_ext", name="Terminal knee extension", kind=REHAB,
        areas=["knee", "quad"], muscles=["quad"], acute=True,
        dose="3 × 15 each leg",
        why="Targets the inner quad, which is what holds the kneecap tracking straight.",
        how=(
            "Loop a band around a fixed point at knee height and around the back of "
            "your knee. Step back to tension, then straighten the knee fully against it."
        ),
    ),

    # ------------------------------------------------------------ hip & glute
    Exercise(
        key="glute_bridge", name="Glute bridge", kind=ACTIVATION,
        areas=["hip", "back", "hamstring"], muscles=["glute", "hamstring"], acute=True,
        dose="3 × 15",
        why=(
            "The glutes extend the hip, which is where running power comes from. When "
            "they are quiet the hamstrings and lower back take the work instead — a "
            "reliable route to a sore back or a pulled hamstring."
        ),
        how=(
            "Lie on your back, knees bent, feet flat. Drive through your heels to lift "
            "your hips until knees, hips and shoulders line up. Squeeze at the top, lower slowly."
        ),
    ),
    Exercise(
        key="single_leg_bridge", name="Single-leg glute bridge", kind=STRENGTH,
        areas=["hip", "hamstring", "back"], muscles=["glute", "hamstring"],
        dose="3 × 10 each side",
        why="The same pattern at roughly double the load, and it exposes a side-to-side difference the double-leg version hides.",
        how="As the glute bridge, with one foot off the floor and that knee hugged toward your chest. Keep the hips level.",
    ),
    Exercise(
        key="clamshell", name="Clamshells", kind=ACTIVATION,
        areas=["hip", "knee", "it_band"], muscles=["glute"], acute=True,
        dose="3 × 15 each side",
        why=(
            "Hip abductor weakness is the single most common finding in runners with "
            "knee or IT band pain. This isolates it with almost no load on the knee itself."
        ),
        how=(
            "Lie on your side, knees bent 45°, feet together. Keeping feet touching "
            "and hips stacked, lift the top knee. Do not let the pelvis roll back."
        ),
    ),
    Exercise(
        key="side_leg_raise", name="Side-lying leg raise", kind=STRENGTH,
        areas=["hip", "it_band", "knee"], muscles=["glute"],
        dose="3 × 12 each side",
        why="Loads the hip abductors through a longer range than clamshells, which is where they work during stance.",
        how="Lie on your side, legs straight and stacked. Raise the top leg to about 45°, slightly behind the line of your body. Lower slowly.",
    ),
    Exercise(
        key="monster_walk", name="Banded lateral walk", kind=ACTIVATION,
        areas=["hip", "knee", "it_band"], muscles=["glute", "quad"],
        dose="3 × 10 steps each direction",
        why="Trains the hip to hold the knee out under load while the foot is on the ground — the position running actually fails in.",
        how="Band around the ankles, quarter-squat. Step sideways keeping tension on the band and feet pointing forward.",
    ),
    Exercise(
        key="hip_flexor_stretch", name="Half-kneeling hip flexor stretch", kind=MOBILITY,
        areas=["hip", "back", "quad"], muscles=["hip_flexor", "quad"], acute=True,
        dose="2 × 30 s each side",
        why=(
            "Sitting all day shortens the hip flexors, which shortens your stride and "
            "makes you reach forward with the foot instead — landing heel-first ahead "
            "of your body, which is exactly the shin-and-knee-loading pattern to avoid."
        ),
        how=(
            "Half-kneeling, back toe tucked. Squeeze the glute on the kneeling side "
            "and shift your weight gently forward. Do not arch your back to get more range."
        ),
    ),

    # ---------------------------------------------------------------- hamstring
    Exercise(
        key="hamstring_curl_slide", name="Sliding hamstring curl", kind=STRENGTH,
        areas=["hamstring", "hip"], muscles=["hamstring", "glute"],
        dose="3 × 10",
        why="Loads the hamstring while the hip is extended, which is the position it is in when it tears.",
        how="Lie on your back, heels on sliders (or a towel on a smooth floor). Bridge up, then slowly slide your heels away and pull them back.",
        caution="Stop at the first sign of cramp; this one is more demanding than it looks.",
    ),
    Exercise(
        key="rdl_single", name="Single-leg Romanian deadlift", kind=STRENGTH,
        areas=["hamstring", "hip", "back", "ankle"], muscles=["hamstring", "glute"],
        dose="3 × 8 each leg",
        why="Builds hamstring and glute strength at length, and trains balance on one leg at the same time — both directly transferable to running.",
        how="Stand on one leg, soft knee. Hinge at the hip, letting the free leg travel back as a counterweight, keeping your back flat. Return under control.",
    ),
    Exercise(
        key="nordic_eccentric", name="Assisted Nordic curl", kind=STRENGTH,
        areas=["hamstring"], muscles=["hamstring"],
        dose="3 × 5, lowering as slowly as you can",
        why="The most effective single exercise for preventing hamstring strains. It is also hard — assist generously and progress patiently.",
        how="Kneel with your ankles anchored. Keeping hips straight, lower your torso forward as slowly as possible, catching yourself with your hands.",
        caution="Expect real soreness for two days after the first session. Start with two reps.",
    ),

    # ------------------------------------------------------------------- back
    Exercise(
        key="dead_bug", name="Dead bug", kind=CORE,
        areas=["back", "hip"], muscles=["core", "hip_flexor"], acute=True,
        dose="3 × 8 each side",
        why=(
            "Teaches the trunk to stay still while the limbs move — which is the "
            "trunk's entire job in running. A back that has to stabilise every stride "
            "is a back that aches by kilometre four."
        ),
        how="Lie on your back, arms up, knees bent 90°. Lower one arm and the opposite leg toward the floor while keeping your lower back flat. Return, swap.",
    ),
    Exercise(
        key="bird_dog", name="Bird dog", kind=CORE,
        areas=["back", "hip"], muscles=["core", "glute"], acute=True,
        dose="3 × 8 each side",
        why="The same anti-rotation demand as the dead bug, upright and loaded through the shoulder and hip together.",
        how="On hands and knees. Extend one arm and the opposite leg until level with your body. Hold 3 s. Keep your hips square to the floor.",
    ),
    Exercise(
        key="side_plank", name="Side plank", kind=CORE,
        areas=["back", "hip", "it_band"], muscles=["core", "glute"],
        dose="3 × 20–40 s each side",
        why="Loads the hip abductors and the side of the trunk together — the pair that stops your pelvis dropping on each landing.",
        how="On your forearm, body in a straight line, hips lifted. Drop to the knees to make it easier rather than letting the hips sag.",
    ),
    Exercise(
        key="cat_cow", name="Cat–cow", kind=MOBILITY,
        areas=["back"], muscles=["core"], acute=True,
        dose="10 slow cycles",
        why="Moves the spine gently through flexion and extension. Best used to settle a stiff back rather than to strengthen it.",
        how="On hands and knees, slowly round then arch your back, breathing with the movement.",
    ),

    # --------------------------------------------------------------- IT band
    Exercise(
        key="it_band_hip_hike", name="Pelvic drop (hip hike)", kind=REHAB,
        areas=["it_band", "hip", "knee"], muscles=["glute"],
        dose="3 × 12 each side",
        why=(
            "IT band pain is a load problem at the hip, not a tight band that needs "
            "rolling out. This trains the muscle that actually controls it."
        ),
        how="Stand sideways on a step, one foot hanging off. Let that hip drop slowly, then lift it by driving the standing glute. Keep both knees straight.",
    ),
    Exercise(
        key="glute_med_wall", name="Wall press hip hold", kind=ACTIVATION,
        areas=["it_band", "hip"], muscles=["glute"], acute=True,
        dose="3 × 20 s each side",
        why="A strong isometric for the hip abductors with no movement, so it is usable while the outside of the knee is still irritable.",
        how="Stand side-on to a wall. Lift the inside knee to 90° and press it hard into the wall. Hold, keeping the standing hip level.",
    ),

    # ------------------------------------------------------------------ groin
    Exercise(
        key="adductor_squeeze", name="Adductor squeeze", kind=REHAB,
        areas=["groin", "hip"], muscles=["groin"], acute=True,
        dose="3 × 10 holds of 5 s",
        why="Groin strains respond to early gentle loading better than to rest. An isometric squeeze is the safest way to start.",
        how="Lie on your back, knees bent, a ball or rolled towel between your knees. Squeeze at about half effort, hold 5 s.",
    ),
    Exercise(
        key="copenhagen", name="Copenhagen plank (short lever)", kind=STRENGTH,
        areas=["groin", "hip", "back"], muscles=["groin", "core"],
        dose="3 × 15 s each side",
        why="The strongest available exercise for the adductors, and one of the few with real evidence behind groin-injury prevention.",
        how="Side plank with your top knee resting on a bench or chair. Lift your bottom leg to meet it. Start with the knee on the bench, not the foot.",
        caution="Begin with the short-lever version only. This gets hard very quickly.",
    ),

    # ------------------------------------------------------------------ drills
    Exercise(
        key="cadence_drill", name="Cadence steps", kind=DRILL,
        areas=["knee", "shin", "foot"], muscles=["calf", "quad"],
        dose="4 × 30 s during an easy walk or jog",
        why=(
            "Quicker, shorter steps put the foot down under your body instead of ahead "
            "of it, which cuts the braking force through the shin and knee. It is the "
            "single highest-return change to running form for a beginner."
            ),
        how="Count your steps on one foot for 30 s. Aim for 40–45, then repeat trying to add two or three — same speed, smaller steps.",
    ),
    Exercise(
        key="a_skip", name="A-skips", kind=DRILL,
        areas=["hip", "calf", "foot"], muscles=["hip_flexor", "calf", "glute"],
        dose="3 × 20 m",
        why="Rehearses the knee-lift and quick ground contact of running at a speed where you can think about it.",
        how="Skip forward driving one knee to hip height, landing under your body on the ball of the foot. Stay tall and relaxed.",
    ),
    Exercise(
        key="strides", name="Strides", kind=DRILL,
        areas=["hamstring", "calf"], muscles=["hamstring", "calf", "glute"],
        dose="4 × 20 s, full recovery between",
        why=(
            "Brief fast running with full recovery. It teaches the legs to turn over "
            "quickly without adding meaningful fatigue — and running only ever slowly "
            "makes running feel harder, not easier."
        ),
        how="Build smoothly to about 85% over 5 s, hold relaxed and tall, then ease down. Walk until fully recovered.",
        caution="Not while anything hurts, and never as an extra hard session — these go at the end of an easy day.",
    ),
]

BY_KEY = {e.key: e for e in CATALOGUE}


def for_area(area: str) -> list[Exercise]:
    """Everything that addresses one body area, rehab and activation first."""
    order = {REHAB: 0, ACTIVATION: 1, MOBILITY: 2, STRENGTH: 3, CORE: 4, DRILL: 5}
    return sorted(
        (e for e in CATALOGUE if area in e.areas),
        key=lambda e: (order.get(e.kind, 9), e.name),
    )


# What a report of pain in one area should actually prescribe. The list is the
# starting routine; anything else for that area is available but not pushed.
FIRST_LINE: dict[str, list[str]] = {
    "foot": ["plantar_roll", "arch_doming", "towel_scrunch", "calf_raise_double"],
    "achilles": ["calf_raise_double", "bent_knee_calf", "knee_to_wall"],
    "calf": ["calf_raise_double", "knee_to_wall", "ankle_alphabet"],
    "shin": ["toe_raise", "heel_walk", "knee_to_wall", "cadence_drill"],
    "knee": ["wall_sit", "clamshell", "terminal_knee_ext", "step_down", "cadence_drill"],
    "it_band": ["glute_med_wall", "clamshell", "it_band_hip_hike", "side_plank"],
    "hip": ["glute_bridge", "clamshell", "hip_flexor_stretch", "side_leg_raise"],
    "hamstring": ["glute_bridge", "single_leg_bridge", "rdl_single"],
    "quad": ["wall_sit", "terminal_knee_ext", "hip_flexor_stretch"],
    "groin": ["adductor_squeeze", "copenhagen"],
    "back": ["cat_cow", "dead_bug", "bird_dog", "glute_bridge"],
    "ankle": ["ankle_alphabet", "knee_to_wall", "calf_raise_double", "calf_raise_single"],
}

# Twice a week, whatever is or is not sore. Chosen to cover the three things that
# most often fail in a new runner: hip abductors, calf capacity, and trunk control.
MAINTENANCE = [
    "glute_bridge", "clamshell", "calf_raise_double", "dead_bug",
    "side_plank", "hip_flexor_stretch",
]

# Presentations that are not a training-load problem and should not be self-managed.
RED_FLAGS = (
    "Pain that wakes you at night, a joint that is visibly swollen or hot, pain "
    "that makes you limp when walking, numbness or pins and needles, or any pain "
    "in one small spot on a bone that gets worse each run — none of those are load "
    "management problems. See a physiotherapist or a doctor rather than working "
    "through this list."
)


def prescription(area: str, severity: int = 2, when: str = "unclear") -> dict:
    """The routine for one reported niggle, plus what to do about running.

    Severity drives whether the acute-safe subset is used; `when` drives the
    training advice, because pain *during* running is a different signal from
    stiffness that shows up the next morning.
    """
    keys = FIRST_LINE.get(area, [])
    picked = [BY_KEY[k] for k in keys if k in BY_KEY]

    # At 4 and above the athlete is telling us it hurts to run on. Only the exercises
    # explicitly safe to load in that state stay in the list.
    acute_only = severity >= 4
    if acute_only:
        picked = [e for e in picked if e.acute]

    if when == "running" and severity >= 3:
        running = (
            "Stop running on this for now. Pain during the run itself, at this level, "
            "is the point at which continuing turns a two-week problem into a "
            "two-month one — and the plan can lose a fortnight and still reach "
            "December. Walk instead; walking keeps the aerobic work going with a "
            "fraction of the load."
        )
    elif when == "running":
        running = (
            "Keep running, but treat this as a ceiling rather than a niggle to push "
            "through: if it gets worse during a session, end the session. Do the work "
            "below on the days between runs."
        )
    elif severity >= 4:
        running = (
            "Not a day to run. Do the gentle work below and reassess tomorrow — if it "
            "is no better in two or three days, that is a physiotherapy question "
            "rather than a training one."
        )
    else:
        running = (
            "Fine to keep running while this settles, as long as it does not worsen "
            "during a session. Add the work below on non-running days."
        )

    return {
        "area": area,
        "severity": severity,
        "when": when,
        "running_advice": running,
        "red_flags": RED_FLAGS,
        "acute_only": acute_only,
        "exercises": [asdict(e) for e in picked],
    }


def catalogue() -> dict:
    """The whole library, grouped for browsing."""
    areas = sorted({a for e in CATALOGUE for a in e.areas})
    return {
        "kind_labels": KIND_LABELS,
        "areas": areas,
        "maintenance": [asdict(BY_KEY[k]) for k in MAINTENANCE if k in BY_KEY],
        "exercises": [asdict(e) for e in CATALOGUE],
        "red_flags": RED_FLAGS,
    }
