"""The athlete's race calendar, resolved to what each day is *for*.

The plan used to know one date. `weeks_out = (race_date - on) // 7` indexed the
17-week table and that was the entire schedule, which works exactly once: for a first
race with a clear run-up. It has nothing to say about the days *after* a race, and
promoting a second race slid the whole ramp onto the new date — so a 10K three weeks
after another 10K prescribed cutback, peak and taper, with peak week landing eight
days after the athlete last raced.

This module sits between the race list and `template.py` and answers a narrower
question: for this date, which of the plan's *modes* applies, and to which race.

    race        — a race is on this date
    recovery    — a race was recently run and is still being repaid
    mini_taper  — a race is close that the 17-week table is not tapering for
    maintenance — a race is coming too soon to build for; hold what you have
    build       — the ordinary 17-week ramp, unchanged
    off_season  — races exist, none of them ahead

Only `build` reads the week table by weeks remaining. That is the whole point: every
other mode exists because the table has no row that is right for those days.

Two rules the modes exist to keep:

**A race is not a training session, and the days after it are not a training week.**
Recovery is prescribed work with its own numbers, not an absence of prescription.

**Never re-enter the ramp mid-block.** Dropping an athlete into `weeks_out=3` two
weeks after a race gives them cutback → peak → taper, which reads as a plan and is
a peak week eight days after a race. When there is no room to build, the plan says
so and holds.

Pure at import — no Django — so the resolution is testable without a database.
`for_athlete` is the one function that touches the ORM, and it imports inside its
own body.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Optional

# Recovery scales with the distance actually raced: roughly one easy day per mile,
# the oldest rule in the sport and still the most defensible one for a beginner.
# Floored at two days because even a 5K time trial is not a Tuesday, and capped at
# three weeks so a marathon cannot silently swallow an entire build.
RECOVERY_DAYS_PER_KM = 0.62
MIN_RECOVERY_DAYS = 2
MAX_RECOVERY_DAYS = 21

# A B-race gets days of taper where the target gets weeks. It is a hard day inside a
# block rather than the thing the block was for, and tapering two weeks for it would
# cost more fitness than the race is worth.
TAPER_DAYS_PER_KM = 0.4
MIN_TAPER_DAYS = 2
MAX_TAPER_DAYS = 10

# The shortest run-in that still contains a real block — `weeks_out` 5 down to 0 is
# cutback, build, peak, taper, race. Below this there is nothing to build, and
# pretending otherwise is how a peak week lands on a recovering athlete.
MIN_BUILD_WEEKS = 6

# How long a race keeps counting against the next one. Past this the body has been
# back to normal training for over a month and a fresh ramp is the right answer.
RE_RACE_WEEKS = 8


def recovery_days(distance_km: float) -> int:
    """Easy days owed after racing `distance_km`.

    Rounded up, not to nearest. A 10K comes out at 6.2 days, and rounding that down
    ends the window on day 6 — which, on a Sunday-long-run week, puts the first run
    back on day 7 as a full long run with no easing step in between. Rounding up
    keeps a short jog between the race and the next real session.
    """
    return int(max(MIN_RECOVERY_DAYS,
                   min(math.ceil(distance_km * RECOVERY_DAYS_PER_KM), MAX_RECOVERY_DAYS)))


def taper_days(distance_km: float) -> int:
    """Days of wind-down before a race the main table is not tapering for."""
    return int(max(MIN_TAPER_DAYS,
                   min(round(distance_km * TAPER_DAYS_PER_KM), MAX_TAPER_DAYS)))


@dataclass(frozen=True)
class RaceRef:
    """A race, reduced to what scheduling needs.

    Deliberately not the Django model: the resolution below is arithmetic on dates
    and distances, and keeping it off the ORM is what lets it be tested directly.
    """

    date: dt.date
    distance_km: float
    label: str = ""
    name: str = ""
    is_target: bool = False

    @property
    def recovery_days(self) -> int:
        return recovery_days(self.distance_km)

    @property
    def taper_days(self) -> int:
        return taper_days(self.distance_km)

    @classmethod
    def from_model(cls, race) -> "RaceRef":
        return cls(
            date=race.race_date,
            distance_km=(race.distance_m or 10000) / 1000,
            label=race.distance_label,
            name=race.name,
            is_target=race.is_target,
        )


@dataclass(frozen=True)
class DayContext:
    """Which mode one date falls in, and the races that put it there."""

    date: dt.date
    mode: str
    # The race the ramp counts down to. Set in every mode that has one ahead of it,
    # not only `build`, because the countdown is still what the UI shows.
    anchor: Optional[RaceRef] = None
    race: Optional[RaceRef] = None          # a race *on* this date
    last_race: Optional[RaceRef] = None     # the most recent one behind it
    next_race: Optional[RaceRef] = None     # the next one ahead
    days_since_race: Optional[int] = None
    days_to_race: Optional[int] = None
    # Plain-language why, shown to the athlete. A day that says "no running" without
    # saying which race it is paying for reads as the plan having lost its place.
    reason: str = ""

    @property
    def weeks_out(self) -> int:
        """Whole weeks to the anchor race, floored. 0 once inside race week."""
        if self.anchor is None:
            return 0
        return max((self.anchor.date - self.date).days // 7, 0)


@dataclass(frozen=True)
class Schedule:
    """Every race an athlete holds, in date order, resolved per day."""

    races: tuple[RaceRef, ...] = field(default_factory=tuple)

    @classmethod
    def of(cls, races) -> "Schedule":
        return cls(tuple(sorted(races, key=lambda r: r.date)))

    @classmethod
    def single(cls, race_date: dt.date, distance_km: float = 10.0) -> "Schedule":
        """One race and nothing else — what the plan assumed before this module.

        Kept so `template.session_for(race_date, on)` still works for previews and
        tests that have no athlete and no database behind them.
        """
        return cls((RaceRef(date=race_date, distance_km=distance_km, is_target=True),))

    def __bool__(self) -> bool:
        return bool(self.races)

    # ------------------------------------------------------------- lookups

    def race_on(self, on: dt.date) -> Optional[RaceRef]:
        return next((r for r in self.races if r.date == on), None)

    def last_before(self, on: dt.date) -> Optional[RaceRef]:
        past = [r for r in self.races if r.date < on]
        return past[-1] if past else None

    def next_after(self, on: dt.date) -> Optional[RaceRef]:
        return next((r for r in self.races if r.date > on), None)

    def anchor(self, on: dt.date) -> Optional[RaceRef]:
        """The race the ramp counts down to.

        The athlete's chosen target while it is still ahead; otherwise simply the
        next race. That fallback is what stops the plan from prescribing race week
        forever once the target has been run — the old code clamped a negative
        `weeks_out` to 0 and kept handing out the race-week row indefinitely.
        """
        ahead = [r for r in self.races if r.date >= on]
        if not ahead:
            return None
        return next((r for r in ahead if r.is_target), ahead[0])

    @property
    def target(self) -> Optional[RaceRef]:
        return next((r for r in self.races if r.is_target), None)

    # ------------------------------------------------------------ the modes

    def context(self, on: dt.date) -> DayContext:
        """Which mode `on` falls in. The one function worth reading in this file."""
        anchor = self.anchor(on)
        last = self.last_before(on)
        nxt = self.next_after(on)
        common = dict(date=on, anchor=anchor, last_race=last, next_race=nxt)

        racing = self.race_on(on)
        if racing is not None:
            return DayContext(
                mode="race", race=racing, days_to_race=0,
                **{**common, "anchor": anchor or racing},
                reason=f"{racing.name or racing.label or 'Race'} is today.",
            )

        if last is not None:
            since = (on - last.date).days
            owed = last.recovery_days
            if since <= owed:
                return DayContext(
                    mode="recovery", days_since_race=since, **common,
                    reason=(
                        f"Day {since} of {owed} after {last.name or last.label}. "
                        f"A {last.distance_km:g} km race is repaid at roughly a day "
                        "per mile, and the repayment is not optional."
                    ),
                )

        if anchor is None:
            return DayContext(
                mode="off_season", **common,
                reason=(
                    "No race ahead. The plan is holding at a level you can keep "
                    "indefinitely — add a race and it re-anchors to that date."
                ),
            )

        # "Am I building?" is a question about the anchor, not about whichever race
        # happens to be next: a B-race two weeks out does not stop a build for an A
        # race in December.
        re_racing = last is not None and (on - last.date).days <= RE_RACE_WEEKS * 7
        weeks_to_anchor = (anchor.date - on).days / 7
        holding = re_racing and weeks_to_anchor < MIN_BUILD_WEEKS

        if nxt is not None:
            to_next = (nxt.date - on).days
            # The table already tapers for the anchor at weeks_out 1 and 0. Every
            # other race needs its own wind-down, and so does the anchor when the
            # plan is holding rather than counting the table down to it.
            table_tapers_for_it = nxt is anchor and not holding
            if not table_tapers_for_it and to_next <= nxt.taper_days:
                return DayContext(
                    mode="mini_taper", days_to_race=to_next, **common,
                    reason=(
                        f"{to_next} day{'s' if to_next != 1 else ''} to "
                        f"{nxt.name or nxt.label}. Nothing you do now makes you "
                        "fitter for it; what you skip keeps you fresh."
                    ),
                )

        if holding:
            gap = (anchor.date - on).days
            return DayContext(
                mode="maintenance", days_to_race=gap, **common,
                reason=(
                    f"{anchor.name or anchor.label} is {gap} days away and you raced "
                    f"{(on - last.date).days} days ago. That is not enough room to "
                    "build, so the plan holds your current level instead of "
                    "restarting the ramp on top of a recovering body."
                ),
            )

        return DayContext(mode="build", days_to_race=(anchor.date - on).days, **common)


# ------------------------------------------------------------------ the ORM edge


def for_athlete(athlete) -> Schedule:
    """Every race this athlete holds. One query, so callers can pass it around."""
    from .models import Race

    return Schedule.of(
        RaceRef.from_model(r) for r in Race.objects.filter(athlete=athlete)
    )


# ------------------------------------------------------------------- timeline


@dataclass(frozen=True)
class Block:
    """A run of consecutive days in the same mode, for the same race.

    The per-day modes are what the plan runs on; this is how a human reads them.
    "Recovery, 7 days, for Bajaj Pune 10K" is the sentence an athlete can check
    against their own intentions — a calendar of 21 individually-correct days is not.
    """

    mode: str
    start: dt.date
    end: dt.date
    race: Optional[RaceRef] = None
    reason: str = ""

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


# The race each mode is *about*, which is not always the one being counted down to.
_BLOCK_RACE = {
    "race": lambda c: c.race,
    "recovery": lambda c: c.last_race,
    "mini_taper": lambda c: c.next_race,
}


def timeline(sched: Schedule, start: dt.date, end: dt.date) -> list[Block]:
    """`start`..`end` collapsed into blocks of like days."""
    blocks: list[Block] = []
    cursor = start
    while cursor <= end:
        ctx = sched.context(cursor)
        race = _BLOCK_RACE.get(ctx.mode, lambda c: c.anchor)(ctx)
        key = (ctx.mode, race.date if race else None)
        if blocks and (blocks[-1].mode, blocks[-1].race.date if blocks[-1].race else None) == key:
            blocks[-1] = Block(blocks[-1].mode, blocks[-1].start, cursor,
                               blocks[-1].race, blocks[-1].reason)
        else:
            blocks.append(Block(ctx.mode, cursor, cursor, race, ctx.reason))
        cursor += dt.timedelta(days=1)
    return blocks


def span(sched: Schedule, today: dt.date) -> tuple[dt.date, dt.date]:
    """The stretch of calendar worth showing: from today to the last race's recovery.

    Bounded by the races themselves rather than by a fixed window, so a schedule
    with nothing on it for six months does not render six months of maintenance.
    """
    if not sched:
        return today, today
    last = sched.races[-1]
    return min(today, sched.races[0].date), max(
        today, last.date + dt.timedelta(days=last.recovery_days)
    )
