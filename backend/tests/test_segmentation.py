"""Segmentation and metrics tests.

The fixture is a real Garmin Instinct 2X recording: 2.65 km in 28:01 that the athlete
described as "couldn't run 2.6 km continuously". Garmin's own lap data shows two laps
and hides the run/walk structure entirely, so this file is the ground truth for the
one thing this system exists to do.
"""

import datetime as dt
from pathlib import Path

import pytest

from apps.analysis.metrics import compute
from apps.analysis.segmentation import Sample, classify, segment
from apps.ingest.fit_parser import parse

FIXTURE = Path(__file__).parent / "fixtures" / "sample_run_2026-08-17.fit"


@pytest.fixture(scope="module")
def parsed():
    return parse(str(FIXTURE))


@pytest.fixture(scope="module")
def segments(parsed):
    return segment(parsed.samples, run_cadence_threshold=140)


class TestParser:
    def test_reads_session_summary(self, parsed):
        assert parsed.sport == "running"
        assert parsed.started_at == dt.datetime(2026, 8, 17, 0, 44, 0)
        assert parsed.total_distance_m == pytest.approx(2650.93, abs=0.1)
        assert parsed.avg_hr == 142
        assert parsed.max_hr == 171

    def test_extracts_per_second_series(self, parsed):
        """The API summary gives 2 laps; the file gives 1,670 samples."""
        assert len(parsed.samples) == 1670

    def test_doubles_per_leg_cadence(self, parsed):
        """FIT stores running cadence per leg. Raw session value is 58; real is ~116+."""
        running = [s.cadence_spm for s in parsed.samples if (s.cadence_spm or 0) >= 140]
        assert running, "expected some samples above the running cadence threshold"
        assert max(running) < 220, "cadence looks doubled twice"


class TestClassification:
    def test_running_cadence_is_run(self):
        assert classify(Sample(0, cadence_spm=168, speed_mps=2.0), 140) == "run"

    def test_walking_cadence_is_walk(self):
        assert classify(Sample(0, cadence_spm=115, speed_mps=1.4), 140) == "walk"

    def test_no_cadence_and_no_speed_is_stop(self):
        assert classify(Sample(0, cadence_spm=0, speed_mps=0.0), 140) == "stop"

    def test_threshold_is_inclusive(self):
        assert classify(Sample(0, cadence_spm=140, speed_mps=2.0), 140) == "run"


class TestSegmentation:
    def test_finds_the_five_run_blocks(self, segments):
        """The headline finding: this was not one continuous run."""
        runs = [s for s in segments if s.kind == "run"]
        assert len(runs) == 5

    def test_longest_continuous_run(self, segments):
        runs = [s for s in segments if s.kind == "run"]
        longest = max(runs, key=lambda s: s.duration_s)
        assert longest.duration_s == pytest.approx(291, abs=2)
        assert longest.distance_m == pytest.approx(581, abs=5)

    def test_run_blocks_collapse_after_the_first(self, segments):
        """Every block after the opening one is under 90 s — the pacing failure."""
        runs = sorted((s for s in segments if s.kind == "run"), key=lambda s: s.start_offset_s)
        assert runs[0].duration_s > 280
        assert all(r.duration_s < 90 for r in runs[1:])

    def test_jitter_does_not_split_a_run_block(self):
        """A single dropped cadence reading must not fracture one run into three."""
        samples = [Sample(offset_s=float(i), cadence_spm=170, speed_mps=2.0, distance_m=2.0 * i)
                   for i in range(300)]
        samples[150].cadence_spm = 0  # one bad reading
        result = segment(samples, 140)
        runs = [s for s in result if s.kind == "run"]
        assert len(runs) == 1
        assert runs[0].duration_s == pytest.approx(299, abs=1)

    def test_empty_input(self):
        assert segment([], 140) == []


class TestHeartRateRecovery:
    def test_measures_recovery_from_peak_not_boundary(self, segments):
        """HR ends the run block at 158, peaks at ~165 twenty seconds into the walk,
        then falls to ~148. Measuring from the boundary would report ~10; from the
        peak, which is the physiological standard, it is ~16."""
        recoveries = [s for s in segments if s.hr_recovery_60s is not None]
        assert len(recoveries) == 1
        assert recoveries[0].hr_recovery_60s == pytest.approx(16, abs=2)

    def test_detects_post_exercise_overshoot(self, segments):
        """HR still climbing after stopping means that block exceeded aerobic capacity."""
        overshoots = [s for s in segments if s.hr_overshoot_bpm is not None]
        assert overshoots[0].hr_overshoot_bpm == pytest.approx(7, abs=2)

    def test_short_run_blocks_do_not_produce_recovery(self, segments):
        """A 45 s run block does not load the athlete enough for HRR60 to mean anything."""
        for seg in segments:
            if seg.hr_recovery_60s is not None:
                idx = segments.index(seg)
                assert segments[idx - 1].duration_s >= 60


@pytest.fixture(scope="module")
def metrics(segments):
    return compute(segments, easy_pace_min=600, easy_pace_max=645, hr_ceiling=155)


class TestMetrics:
    def test_separates_run_from_walk_distance(self, metrics):
        assert metrics.run_distance_m == pytest.approx(976, abs=10)
        assert metrics.walk_distance_m == pytest.approx(1522, abs=15)

    def test_average_running_pace(self, metrics):
        """8:27/km — roughly 90 s/km faster than the prescribed easy band."""
        assert metrics.avg_run_pace_s_per_km == pytest.approx(507, abs=5)

    def test_cadence_is_already_good(self, metrics):
        """168 spm needs no coaching; the fix is stride length, not turnover."""
        assert metrics.avg_run_cadence_spm == pytest.approx(168.7, abs=1.0)

    def test_pace_discipline_is_near_zero(self, metrics):
        """Almost no running time was inside the 10:00-10:45/km band."""
        assert metrics.pace_discipline_pct < 5.0

    def test_hr_ceiling_breached_for_much_of_the_run(self, metrics):
        assert metrics.hr_over_ceiling_pct == pytest.approx(38.2, abs=2.0)

    def test_pace_discipline_rewards_a_correctly_paced_run(self):
        """Same shape of session, run at 10:20/km, should score near 100%."""
        speed = 1000 / 620  # 10:20 per km
        samples = [Sample(offset_s=float(i), cadence_spm=168, speed_mps=speed,
                          distance_m=speed * i, heart_rate=138) for i in range(600)]
        result = compute(segment(samples, 140), 600, 645, 155)
        assert result.pace_discipline_pct > 95.0
        assert result.hr_over_ceiling_pct == 0.0
