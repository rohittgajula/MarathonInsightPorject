"""What to drink and eat around a session, scaled to the session and the weather.

The plan already knows how long the athlete will be out and what the air will be
doing while they are — those two numbers are most of the answer, and neither is
guesswork. What was missing was turning them into quantities.

Heat is the reason this matters here more than it would elsewhere. Training happens
in Telangana, where a "mild" morning is 29 °C at 80% humidity. Above roughly 70%
humidity, sweat stops evaporating efficiently: it runs off instead of cooling, so
the body sweats harder for less cooling and fluid loss climbs while the benefit
falls. A hydration rule written for a temperate climate under-reads that badly.

Every number below is derived from the session and the forecast and shown with the
figure it came from — the same standard the rest of the app is held to. The ranges
are the conventional sports-nutrition ones; the arithmetic is what makes them
specific to this session rather than general advice.

Fluid guidance is deliberately expressed as "drink to thirst, within this range".
Prescribing a fixed volume to force down is how people over-drink, and over-drinking
in the heat is more dangerous than mild dehydration, not less.
"""

from __future__ import annotations

from typing import Optional

# Sweat rate for easy running in temperate conditions, litres per hour. The
# population range is wide (0.3–2.4 L/h); this is a conservative middle for a
# beginner at easy pace, and the output is a range rather than a single figure.
BASE_SWEAT_L_PER_H = 0.5

# Sweat loss climbs with apparent temperature above a comfortable baseline.
COMFORT_C = 20.0
SWEAT_PER_DEGREE = 0.035  # +3.5% per °C of apparent temperature above comfort

# Above this, evaporative cooling starts failing and sweat runs off without cooling.
HUMID_PCT = 70.0
HUMID_PENALTY = 0.20  # +20% on top, once humidity is high enough to matter

# Sodium concentration in sweat, mg per litre. Individual range is 200–2000; this is
# a working middle. Salty sweaters (visible white marks on clothing) sit well above it.
SODIUM_MG_PER_L = 700

# A walk loses meaningfully less fluid than a run at the same duration.
WALK_FACTOR = 0.65

# Sessions at or under this need no carbohydrate beforehand — the muscle already
# holds far more than the session will spend.
NO_FOOD_MINUTES = 45
# Beyond this, fluid taken during the session starts to matter rather than being optional.
DRINK_DURING_MINUTES = 30
# Beyond this, or in real heat, water alone stops being enough.
ELECTROLYTE_MINUTES = 60

DEFAULT_WEIGHT_KG = 70.0

RUN_KINDS = {"intervals", "long", "jog", "race"}


def _sweat_multiplier(feels_like_c: Optional[float], humidity_pct: Optional[float]) -> tuple[float, list[str]]:
    """How much harder than temperate conditions this session will be on fluid."""
    multiplier = 1.0
    reasons: list[str] = []

    if feels_like_c is not None and feels_like_c > COMFORT_C:
        degrees = feels_like_c - COMFORT_C
        bump = degrees * SWEAT_PER_DEGREE
        multiplier += bump
        reasons.append(
            f"{feels_like_c:.0f} °C feels-like is {degrees:.0f} °C above comfortable, "
            f"which raises fluid loss by roughly {bump * 100:.0f}%"
        )

    if humidity_pct is not None and humidity_pct >= HUMID_PCT:
        multiplier += HUMID_PENALTY
        reasons.append(
            f"at {humidity_pct:.0f}% humidity sweat cannot evaporate properly, so it "
            "runs off without cooling you — you lose the fluid and keep the heat"
        )

    return multiplier, reasons


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def plan(athlete, session, conditions: Optional[dict] = None) -> dict:
    """Fluid, food and salt for one session.

    `session` is a PlannedSession; `conditions` is a `weather.forecast` result, which
    may be empty when no location is known — in that case the temperate baseline is
    used and the response says so.
    """
    conditions = conditions or {}
    feels_like = conditions.get("feels_like_c")
    humidity = conditions.get("humidity_pct")
    weight = getattr(athlete, "weight_kg", None) or DEFAULT_WEIGHT_KG
    weight_assumed = not getattr(athlete, "weight_kg", None)

    minutes = float(getattr(session, "total_minutes", 0) or 0)
    kind = getattr(session, "kind", "rest")
    is_run = kind in RUN_KINDS
    hours = minutes / 60.0

    multiplier, heat_reasons = _sweat_multiplier(feels_like, humidity)
    rate = BASE_SWEAT_L_PER_H * multiplier * (1.0 if is_run else WALK_FACTOR)
    expected_loss_ml = rate * hours * 1000

    hot = bool(
        (feels_like is not None and feels_like >= 28)
        or (humidity is not None and humidity >= HUMID_PCT)
    )

    # ---------------------------------------------------------------- before
    # 5–7 ml/kg two to four hours out is the standard pre-exercise loading range.
    pre_low = _round_to(5 * weight, 50)
    pre_high = _round_to(7 * weight, 50)
    before: list[dict] = [{
        "key": "pre_water",
        "label": "Water, 2 hours before",
        "amount": f"{pre_low}–{pre_high} ml",
        "detail": (
            f"About 5–7 ml per kg of body weight ({weight:.0f} kg). Two hours out, so "
            "there is time to pass what you do not need — drinking it at the door "
            "just means running with it."
        ),
    }]

    if hot:
        top_up = _round_to(3 * weight, 50)
        before.append({
            "key": "pre_topup",
            "label": "Top-up, 15 minutes before",
            "amount": f"{top_up} ml",
            "detail": (
                "A small extra in the heat. You start losing fluid within the first "
                "few minutes here, so starting slightly ahead is worth more than it "
                "would be in cooler air."
            ),
        })

    if minutes <= NO_FOOD_MINUTES:
        before.append({
            "key": "pre_food",
            "label": "Food",
            "amount": "Not needed",
            "detail": (
                f"At {minutes:.0f} minutes you are nowhere near the limits of what "
                "your muscles already hold. If you have not eaten for several hours "
                "and feel empty, a banana or a couple of dates 45 minutes before is "
                "plenty — it is for comfort, not for fuel."
            ),
        })
    else:
        carbs = _round_to(1.0 * weight, 5)
        before.append({
            "key": "pre_food",
            "label": "Carbohydrate, 90 minutes before",
            "amount": f"~{carbs} g",
            "detail": (
                f"About 1 g per kg ({weight:.0f} kg) — two slices of toast with jam, "
                "a large banana with honey, or a bowl of poha. Keep it low in fat and "
                "fibre; both slow the stomach down and neither helps you run."
            ),
        })

    if hot:
        before.append({
            "key": "pre_salt",
            "label": "Salt, with the pre-run drink",
            "amount": "¼ tsp salt in 500 ml, or one electrolyte tablet",
            "detail": (
                "Roughly 500 mg of sodium. In this heat it does more than the water "
                "alone: sodium is what keeps the fluid in circulation instead of "
                "passing straight through you."
            ),
        })

    # ---------------------------------------------------------------- during
    during: list[dict] = []
    if minutes <= 0 or not (is_run or kind == "walk"):
        during.append({
            "key": "during_none",
            "label": "Nothing prescribed",
            "amount": "—",
            "detail": "No session today. Drink normally to thirst.",
        })
    elif minutes < DRINK_DURING_MINUTES and not hot:
        during.append({
            "key": "during_short",
            "label": "Carrying water",
            "amount": "Optional",
            "detail": (
                f"{minutes:.0f} minutes in mild conditions — you can finish this "
                "comfortably without drinking. Carry water if it makes you more "
                "likely to go out, not because the session needs it."
            ),
        })
    else:
        # Replacing 60–80% of loss during the session is the usual target; chasing
        # 100% tends to mean a sloshing stomach rather than better hydration.
        low = _round_to(expected_loss_ml * 0.6, 50)
        high = _round_to(expected_loss_ml * 0.8, 50)
        per_hour = _round_to(rate * 1000 * 0.7, 50)
        during.append({
            "key": "during_water",
            "label": "Water during the session",
            "amount": f"{low}–{high} ml" if low else "Sip to thirst",
            "detail": (
                f"You will lose roughly {_round_to(expected_loss_ml, 50)} ml over "
                f"{minutes:.0f} minutes in these conditions — about {per_hour} ml an "
                "hour is the replacement rate. Drink to thirst inside that range "
                "rather than forcing it down: a few small mouthfuls every ten minutes "
                "sits better than one large drink."
            ),
        })

    if (minutes >= ELECTROLYTE_MINUTES or hot) and (is_run or kind == "walk") and minutes > 0:
        sodium = _round_to((expected_loss_ml / 1000) * SODIUM_MG_PER_L * 0.7, 50)
        during.append({
            "key": "during_salt",
            "label": "Electrolytes",
            "amount": f"~{sodium} mg sodium" if sodium >= 100 else "Not needed",
            "detail": (
                "Sweat carries roughly 700 mg of sodium per litre. In this heat plain "
                "water replaces the volume and dilutes what is left, which is what "
                "produces the headache and the flat feeling afterwards. One "
                "electrolyte tablet in your bottle covers it; a pinch of salt and a "
                "squeeze of lemon does the same job."
            ) if sodium >= 100 else (
                "Short enough and mild enough that plain water is fine."
            ),
        })

    # ----------------------------------------------------------------- after
    after: list[dict] = []
    if minutes > 0 and (is_run or kind == "walk"):
        replace = _round_to(expected_loss_ml * 1.3, 50)
        after.append({
            "key": "post_water",
            "label": "Rehydrate",
            "amount": f"{replace} ml over the next 2 hours",
            "detail": (
                "About 1.3× what you lost — some of what you drink leaves as urine "
                "before it is absorbed, so replacing exactly the deficit leaves you "
                "short. Spread it out rather than drinking it at once."
            ),
        })
        after.append({
            "key": "post_salt",
            "label": "Salt with the next meal",
            "amount": "Normal salted food",
            "detail": (
                "Nothing special needed — a normally salted meal replaces the sodium "
                "from a session this length. This is the one time a salty meal is "
                "working for you rather than against you."
            ),
        })

    # ----------------------------------------------------------------- notes
    notes: list[str] = []
    if heat_reasons:
        notes.append(
            "Adjusted for conditions: " + "; ".join(heat_reasons) + "."
        )
    else:
        notes.append(
            "No forecast available for this session, so these are temperate-weather "
            "figures. They will under-read on a hot morning."
            if not conditions else
            "Conditions are mild enough that no heat adjustment was applied."
        )
    if weight_assumed:
        notes.append(
            f"Body weight is not set, so {DEFAULT_WEIGHT_KG:.0f} kg was assumed. "
            "Setting it makes every number here specific to you rather than typical."
        )
    notes.append(
        "Drink to thirst inside these ranges. Over-drinking in heat dilutes your "
        "blood sodium, which is more dangerous than being mildly under-hydrated — "
        "the ranges are a ceiling as much as a target."
    )

    return {
        "session_title": getattr(session, "title", ""),
        "minutes": minutes,
        "is_run": is_run,
        "hot": hot,
        "weight_kg": weight,
        "weight_assumed": weight_assumed,
        "feels_like_c": feels_like,
        "humidity_pct": humidity,
        "sweat_rate_ml_per_h": _round_to(rate * 1000, 10),
        "expected_loss_ml": _round_to(expected_loss_ml, 10),
        "before": before,
        "during": during,
        "after": after,
        "notes": notes,
    }
