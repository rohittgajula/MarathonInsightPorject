"""Per-activity derived metrics.

Everything here is recomputed from records + segments and never hand-authored, so a
change to the segmentation algorithm can be rolled across the full history by simply
re-running it.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Optional, Sequence

from .segmentation import ALGORITHM_VERSION, Sample, SegmentResult

# GPS speed is jittery second to second; pace judgements are made on a rolling mean
# rather than raw samples, otherwise discipline scores swing wildly on a steady run.
PACE_SMOOTHING_S = 15


@dataclass
class ActivityMetricsResult:
    run_time_s: float = 0.0
    walk_time_s: float = 0.0
    stop_time_s: float = 0.0
    run_distance_m: float = 0.0
    walk_distance_m: float = 0.0
    run_block_count: int = 0
    longest_run_s: float = 0.0
    longest_run_m: float = 0.0
    avg_run_pace_s_per_km: Optional[float] = None
    avg_run_cadence_spm: Optional[float] = None
    pace_discipline_pct: Optional[float] = None
    hr_over_ceiling_pct: Optional[float] = None
    avg_hr_recovery_60s: Optional[float] = None
    avg_hr_overshoot_bpm: Optional[float] = None
    algorithm_version: int = ALGORITHM_VERSION

    def as_dict(self) -> dict:
        return asdict(self)


def _smoothed_speeds(samples: Sequence[Sample]) -> list[float]:
    """Centred rolling mean of speed, in m/s, aligned to `samples`."""
    speeds = [s.speed_mps or 0.0 for s in samples]
    half = PACE_SMOOTHING_S // 2
    out = []
    for i in range(len(speeds)):
        lo = max(0, i - half)
        hi = min(len(speeds), i + half + 1)
        window = speeds[lo:hi]
        out.append(statistics.mean(window) if window else 0.0)
    return out


def compute(
    segments: Sequence[SegmentResult],
    easy_pace_min: float,
    easy_pace_max: float,
    hr_ceiling: int,
) -> ActivityMetricsResult:
    result = ActivityMetricsResult()

    run_segments = [s for s in segments if s.kind == "run"]
    result.run_block_count = len(run_segments)

    for seg in segments:
        if seg.kind == "run":
            result.run_time_s += seg.duration_s
            result.run_distance_m += seg.distance_m
        elif seg.kind == "walk":
            result.walk_time_s += seg.duration_s
            result.walk_distance_m += seg.distance_m
        else:
            result.stop_time_s += seg.duration_s

    if run_segments:
        longest_by_time = max(run_segments, key=lambda s: s.duration_s)
        result.longest_run_s = longest_by_time.duration_s
        result.longest_run_m = longest_by_time.distance_m

        if result.run_time_s > 0 and result.run_distance_m > 1:
            result.avg_run_pace_s_per_km = result.run_time_s / (result.run_distance_m / 1000.0)

        cadences = [s.avg_cadence_spm for s in run_segments if s.avg_cadence_spm]
        if cadences:
            result.avg_run_cadence_spm = round(statistics.mean(cadences), 1)

    # Pace discipline and HR ceiling breaches are judged only over running seconds —
    # walking slower than the easy band is the plan working, not a failure.
    in_band = total_run_samples = over_ceiling = hr_samples = 0
    for seg in run_segments:
        smoothed = _smoothed_speeds(seg.samples)
        for sample, speed in zip(seg.samples, smoothed):
            total_run_samples += 1
            if speed > 0.1:
                pace = 1000.0 / speed
                if easy_pace_min <= pace <= easy_pace_max:
                    in_band += 1
            if sample.heart_rate:
                hr_samples += 1
                if sample.heart_rate > hr_ceiling:
                    over_ceiling += 1

    if total_run_samples:
        result.pace_discipline_pct = round(100.0 * in_band / total_run_samples, 1)
    if hr_samples:
        result.hr_over_ceiling_pct = round(100.0 * over_ceiling / hr_samples, 1)

    recoveries = [s.hr_recovery_60s for s in segments if s.hr_recovery_60s is not None]
    if recoveries:
        result.avg_hr_recovery_60s = round(statistics.mean(recoveries), 1)

    overshoots = [s.hr_overshoot_bpm for s in segments if s.hr_overshoot_bpm is not None]
    if overshoots:
        result.avg_hr_overshoot_bpm = round(statistics.mean(overshoots), 1)

    return result
