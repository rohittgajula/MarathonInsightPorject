"""Race-calendar resolution: which mode each day is in, and what it prescribes.

These are the tests the plan layer never had. They need no database and no athlete —
`schedule.py` is arithmetic on dates and distances, and `template.session_in` falls
back to a default training week when given no athlete, so the whole prescription path
is reachable from a plain unit test.

The case that motivated all of this is `test_second_race_three_weeks_later`: two 10Ks
21 days apart, which the single-date plan turned into cutback, peak and taper with
peak week landing eight days after the first race.
"""

import datetime as dt

import pytest

from apps.plans import schedule as sched
from apps.plans.template import MAINTENANCE, WEEKS, session_in

# 13 December 2026 is a Sunday, and so is 3 January 2027 — the real pair that
# exposed the problem. The default training week puts the long run on Sunday.
TARGET_DAY = dt.date(2026, 12, 13)
SECOND_DAY = dt.date(2027, 1, 3)


def race(date, km=10.0, target=False, name="Race"):
    return sched.RaceRef(date=date, distance_km=km, label=f"{km:g}K",
                         name=name, is_target=target)


def modes(schedule, start, days):
    return [schedule.context(start + dt.timedelta(days=i)).mode for i in range(days)]


def sessions(schedule, start, days):
    return [session_in(schedule, start + dt.timedelta(days=i)) for i in range(days)]


# ------------------------------------------------------------------- windows


@pytest.mark.parametrize("km,expected", [(5, 4), (10, 7), (21.097, 14), (42.195, 21)])
def test_recovery_scales_with_distance(km, expected):
    """Roughly a day per mile, rounded up, capped at three weeks."""
    assert sched.recovery_days(km) == expected


@pytest.mark.parametrize("km,expected", [(5, 2), (10, 4), (21.097, 8), (42.195, 10)])
def test_taper_scales_with_distance(km, expected):
    assert sched.taper_days(km) == expected


# -------------------------------------------------------------------- anchor


def test_target_anchors_the_ramp_while_it_is_ahead():
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(SECOND_DAY)])
    assert s.anchor(dt.date(2026, 10, 1)).date == TARGET_DAY


def test_anchor_moves_to_the_next_race_once_the_target_is_run():
    """The old code clamped a negative weeks_out to 0 and prescribed race week forever."""
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(SECOND_DAY)])
    assert s.anchor(dt.date(2026, 12, 20)).date == SECOND_DAY


def test_no_anchor_once_every_race_is_behind():
    s = sched.Schedule.of([race(TARGET_DAY, target=True)])
    assert s.anchor(dt.date(2027, 6, 1)) is None


# ------------------------------------------------- the case this was built for


def test_second_race_three_weeks_later():
    """Race, recovery, hold, taper, race — and never a peak week in between."""
    s = sched.Schedule.of([
        race(TARGET_DAY, target=True, name="Bajaj Pune 10K"),
        race(SECOND_DAY, name="New Year 10K"),
    ])
    got = modes(s, TARGET_DAY, 22)

    assert got[0] == "race"
    assert got[1:8] == ["recovery"] * 7          # 10K is repaid over seven days
    assert set(got[8:17]) == {"maintenance"}     # no room to build, so hold
    assert got[17:21] == ["mini_taper"] * 4      # the second race gets four days
    assert got[21] == "race"


def test_the_gap_never_prescribes_more_than_maintenance():
    """The failure the modes exist to prevent: peak week eight days after a race."""
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(SECOND_DAY)])
    peak_long_km = WEEKS[2][3]
    between = [x for x in sessions(s, TARGET_DAY + dt.timedelta(days=1), 20) if x]

    assert max(x.distance_km for x in between) <= MAINTENANCE[3]
    assert all(x.distance_km < peak_long_km for x in between)
    assert all(x.plan_week is None for x in between)


def test_first_run_back_is_a_short_jog_not_a_long_run():
    """Recovery has to end on an easing step, not hand straight over to a long run."""
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(SECOND_DAY)])
    runs = [x for x in sessions(s, TARGET_DAY + dt.timedelta(days=1), 10)
            if x.kind in ("jog", "long", "intervals")]

    assert runs[0].kind == "jog"
    assert runs[0].distance_km == 3.5
    assert runs[0].mode == "recovery"


# ------------------------------------------------------------------ recovery


def test_recovery_starts_with_complete_rest():
    s = sched.Schedule.of([race(TARGET_DAY, target=True)])
    day_one = session_in(s, TARGET_DAY + dt.timedelta(days=1))

    assert day_one.kind == "rest"
    assert day_one.total_minutes == 0
    assert not day_one.optional


def test_recovery_never_adds_work_to_a_rest_day():
    """Recovery only ever replaces a session with something smaller."""
    s = sched.Schedule.of([race(TARGET_DAY, target=True)])
    # Wednesday and Friday are rest days in the default week.
    for offset in (3, 5):
        day = session_in(s, TARGET_DAY + dt.timedelta(days=offset))
        assert day.kind == "rest", offset


def test_recovery_ends_and_the_plan_resumes():
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(SECOND_DAY)])
    owed = sched.recovery_days(10.0)

    assert s.context(TARGET_DAY + dt.timedelta(days=owed)).mode == "recovery"
    assert s.context(TARGET_DAY + dt.timedelta(days=owed + 1)).mode != "recovery"


# ------------------------------------------------------------- B-race in a block


def test_b_race_mid_build_returns_to_the_ramp():
    """A 5K in October is a hard day inside the December block, not a new plan."""
    b_race = dt.date(2026, 10, 4)
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(b_race, km=5.0)])

    assert s.context(b_race - dt.timedelta(days=1)).mode == "mini_taper"
    assert s.context(b_race).mode == "race"
    assert s.context(b_race + dt.timedelta(days=2)).mode == "recovery"
    # Four days of recovery for a 5K, then straight back into the ramp.
    resumed = s.context(b_race + dt.timedelta(days=5))
    assert resumed.mode == "build"
    assert resumed.anchor.date == TARGET_DAY


def test_b_race_taper_is_days_not_weeks():
    """The table's two-week taper is far too expensive for a race inside a block."""
    b_race = dt.date(2026, 10, 4)
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(b_race, km=5.0)])

    assert s.context(b_race - dt.timedelta(days=2)).mode == "mini_taper"
    assert s.context(b_race - dt.timedelta(days=3)).mode == "build"


def test_race_day_uses_its_own_distance():
    """A 5K prescribed as the week table's 10 km long run was the old behaviour."""
    b_race = dt.date(2026, 10, 4)
    s = sched.Schedule.of([race(TARGET_DAY, target=True), race(b_race, km=5.0)])
    day = session_in(s, b_race)

    assert day.kind == "race"
    assert day.distance_km == 5.0
    assert "not your target race" in day.detail


def test_the_target_race_is_not_hedged():
    s = sched.Schedule.of([race(TARGET_DAY, target=True)])
    assert "not your target race" not in session_in(s, TARGET_DAY).detail


# --------------------------------------------------------------- single race


def test_a_lone_race_does_not_prescribe_race_week_forever():
    """The bug a clamped negative `weeks_out` produced: 10 km every Sunday, for good."""
    s = sched.Schedule.single(TARGET_DAY)
    later = session_in(s, TARGET_DAY + dt.timedelta(days=30))

    assert later.mode == "off_season"
    assert later.plan_week is None
    assert later.distance_km <= MAINTENANCE[3]


def test_an_ordinary_run_up_is_unchanged():
    """Everything above is additive: one race, still ahead, still reads the table."""
    s = sched.Schedule.single(TARGET_DAY)
    on = TARGET_DAY - dt.timedelta(weeks=9)
    day = session_in(s, on)

    assert day.mode == "build"
    assert day.plan_week == 8
    assert day.weeks_out == 9
    assert day.title == "Long run — 5 km"


def test_dates_before_the_plan_are_still_flagged():
    s = sched.Schedule.single(TARGET_DAY)
    day = session_in(s, TARGET_DAY - dt.timedelta(weeks=30))

    assert day.before_plan
    assert day.plan_week == 1


def test_no_races_means_no_prescription():
    assert session_in(sched.Schedule.of([]), TARGET_DAY) is None


def test_a_close_race_from_cold_still_builds():
    """Maintenance is for re-racing. With no race behind you, the ramp is unchanged."""
    s = sched.Schedule.single(TARGET_DAY)
    assert s.context(TARGET_DAY - dt.timedelta(weeks=3)).mode == "build"


# ---------------------------------------------------------------- timeline


def test_timeline_collapses_days_into_readable_blocks():
    s = sched.Schedule.of([
        race(TARGET_DAY, target=True, name="Bajaj Pune 10K"),
        race(SECOND_DAY, name="New Year 10K"),
    ])
    blocks = sched.timeline(s, TARGET_DAY, SECOND_DAY)

    assert [b.mode for b in blocks] == [
        "race", "recovery", "maintenance", "mini_taper", "race",
    ]
    assert [b.days for b in blocks] == [1, 7, 9, 4, 1]
    assert blocks[1].race.name == "Bajaj Pune 10K"    # recovery belongs to the first
    assert blocks[3].race.name == "New Year 10K"      # the taper to the second


def test_span_covers_the_last_race_and_its_recovery():
    s = sched.Schedule.of([race(TARGET_DAY, target=True)])
    start, end = sched.span(s, dt.date(2026, 12, 1))

    assert start == dt.date(2026, 12, 1)
    assert end == TARGET_DAY + dt.timedelta(days=7)
