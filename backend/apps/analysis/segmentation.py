"""Run / walk / stop segmentation from per-second samples.

Deliberately free of Django imports so it can be unit-tested and reused offline.

Why cadence and not speed: GPS speed is noisy enough that a slow jog and a brisk
walk overlap heavily, and it drifts badly under tree cover or between buildings.
Cadence separates them cleanly — walking sits around 100-125 steps/min and running
almost never drops below 140, regardless of how slow the runner is going.

Bump ALGORITHM_VERSION whenever the classification changes; stored metrics carry
the version they were computed under so old activities can be found and reprocessed.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional

ALGORITHM_VERSION = 1

Kind = Literal["run", "walk", "stop"]

# A block shorter than this is treated as sensor jitter rather than a real change of
# gait, and is absorbed into the surrounding block.
MIN_SEGMENT_S = 8.0

# Recovery must span at least this long for HRR60 to be meaningful.
MIN_RECOVERY_S = 60.0

# A run block shorter than this doesn't load the athlete enough for the following
# recovery to say anything about fitness.
MIN_RUN_FOR_RECOVERY_S = 60.0

STOP_CADENCE = 30.0
STOP_SPEED_MPS = 0.4


@dataclass
class Sample:
    offset_s: float
    distance_m: Optional[float] = None
    speed_mps: Optional[float] = None
    cadence_spm: Optional[float] = None
    heart_rate: Optional[int] = None


@dataclass
class SegmentResult:
    index: int
    kind: Kind
    start_offset_s: float
    duration_s: float
    distance_m: float
    avg_pace_s_per_km: Optional[float] = None
    avg_cadence_spm: Optional[float] = None
    hr_start: Optional[int] = None
    hr_end: Optional[int] = None
    hr_avg: Optional[int] = None
    hr_max: Optional[int] = None
    hr_recovery_60s: Optional[int] = None
    hr_overshoot_bpm: Optional[int] = None
    samples: list[Sample] = field(default_factory=list, repr=False)


def classify(sample: Sample, run_cadence_threshold: float) -> Kind:
    cad = sample.cadence_spm or 0.0
    speed = sample.speed_mps or 0.0
    if cad >= run_cadence_threshold:
        return "run"
    if cad < STOP_CADENCE or speed < STOP_SPEED_MPS:
        return "stop"
    return "walk"


def _median_hr(samples: list[Sample], lo: float, hi: float) -> Optional[int]:
    """Median HR for samples with offset in [lo, hi). Median resists the single-beat
    spikes that optical wrist sensors produce, which a raw endpoint read would not."""
    vals = [s.heart_rate for s in samples if s.heart_rate and lo <= s.offset_s < hi]
    return int(statistics.median(vals)) if vals else None


def _finalise(seg: SegmentResult) -> SegmentResult:
    samples = seg.samples
    if not samples:
        return seg

    first, last = samples[0], samples[-1]
    seg.duration_s = max(last.offset_s - first.offset_s, 0.0)

    if first.distance_m is not None and last.distance_m is not None:
        seg.distance_m = max(last.distance_m - first.distance_m, 0.0)
    else:
        # Fall back to integrating speed when the device gave no cumulative distance.
        seg.distance_m = sum((s.speed_mps or 0.0) for s in samples[1:])

    if seg.duration_s > 0 and seg.distance_m > 1:
        seg.avg_pace_s_per_km = seg.duration_s / (seg.distance_m / 1000.0)

    cadences = [s.cadence_spm for s in samples if s.cadence_spm]
    if cadences:
        seg.avg_cadence_spm = round(statistics.mean(cadences), 1)

    hrs = [s.heart_rate for s in samples if s.heart_rate]
    if hrs:
        seg.hr_avg = int(statistics.mean(hrs))
        seg.hr_max = max(hrs)
        start = first.offset_s
        seg.hr_start = _median_hr(samples, start, start + 5) or hrs[0]
        seg.hr_end = _median_hr(samples, last.offset_s - 5, last.offset_s + 1) or hrs[-1]

    return seg


def segment(samples: Iterable[Sample], run_cadence_threshold: float = 140.0) -> list[SegmentResult]:
    """Split an ordered sample series into run/walk/stop blocks."""
    ordered = sorted(samples, key=lambda s: s.offset_s)
    if not ordered:
        return []

    raw: list[SegmentResult] = []
    for s in ordered:
        kind = classify(s, run_cadence_threshold)
        if raw and raw[-1].kind == kind:
            raw[-1].samples.append(s)
        else:
            raw.append(
                SegmentResult(
                    index=len(raw), kind=kind, start_offset_s=s.offset_s,
                    duration_s=0.0, distance_m=0.0, samples=[s],
                )
            )

    merged = _merge_jitter(raw)
    for i, seg in enumerate(merged):
        seg.index = i
        seg.start_offset_s = seg.samples[0].offset_s
        _finalise(seg)

    _attach_recovery(merged)
    return merged


def _merge_jitter(segs: list[SegmentResult]) -> list[SegmentResult]:
    """Absorb sub-MIN_SEGMENT_S blocks into the preceding block.

    Without this a single dropped cadence reading mid-run splits one 5-minute run
    block into three, which would badly understate the athlete's longest continuous run.
    """
    if not segs:
        return []

    out: list[SegmentResult] = [segs[0]]
    for seg in segs[1:]:
        span = seg.samples[-1].offset_s - seg.samples[0].offset_s
        if span < MIN_SEGMENT_S:
            out[-1].samples.extend(seg.samples)
        else:
            out.append(seg)

    # Merging can leave two same-kind blocks adjacent; collapse them.
    collapsed: list[SegmentResult] = [out[0]]
    for seg in out[1:]:
        if seg.kind == collapsed[-1].kind:
            collapsed[-1].samples.extend(seg.samples)
        else:
            collapsed.append(seg)
    return collapsed


def _smoothed_peak_hr(samples: list[Sample], lo: float, hi: float) -> Optional[int]:
    """Highest 5-second median HR in the window, so one spurious beat can't set the peak."""
    windowed = [s for s in samples if s.heart_rate and lo <= s.offset_s <= hi]
    if not windowed:
        return None
    peaks = []
    for s in windowed:
        med = _median_hr(windowed, s.offset_s - 2, s.offset_s + 3)
        if med is not None:
            peaks.append(med)
    return max(peaks) if peaks else None


def _attach_recovery(segs: list[SegmentResult]) -> None:
    """Derive two distinct heart-rate signals from each qualifying recovery block.

    `hr_recovery_60s` (HRR60) is the standard fitness marker: peak heart rate minus
    heart rate 60 s later. It is measured from the peak rather than from the moment
    running stopped, because cardiac lag means HR typically keeps climbing for
    15-25 s into recovery — measuring from the block boundary understates the drop.
    This number should climb over months as aerobic fitness improves.

    `hr_overshoot_bpm` is how much further HR rose *after* the athlete stopped
    running. A large overshoot means the run block outran their aerobic system.
    This number should fall towards zero as base fitness improves, and is the
    metric that flags "you ran that block too fast" on a per-block basis.
    """
    for i, seg in enumerate(segs):
        if seg.kind not in ("walk", "stop") or i == 0:
            continue
        prev = segs[i - 1]
        if prev.kind != "run" or prev.duration_s < MIN_RUN_FOR_RECOVERY_S:
            continue
        if seg.duration_s < MIN_RECOVERY_S:
            continue

        run_end = prev.samples[-1].offset_s
        # Peak may sit either side of the boundary, so search across both blocks.
        around_boundary = prev.samples + seg.samples
        peak = _smoothed_peak_hr(around_boundary, run_end - 10, run_end + 30)
        hr_at_60 = _median_hr(seg.samples, run_end + 55, run_end + 65)
        hr_at_end_of_run = _median_hr(prev.samples, run_end - 5, run_end + 1)

        if peak is not None and hr_at_60 is not None:
            seg.hr_recovery_60s = peak - hr_at_60
        if peak is not None and hr_at_end_of_run is not None:
            seg.hr_overshoot_bpm = max(peak - hr_at_end_of_run, 0)
