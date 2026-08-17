"""Cross-activity comparison series.

Two runs are never the same length or the same duration, so comparing them by elapsed
time would line up minute 5 of a 2 km jog with minute 5 of an 8 km long run — which
says nothing. Everything here is resampled onto **distance**, so the same point on the
x-axis is the same point on the route for every run being compared.

Series are downsampled to a fixed number of buckets. A 28-minute run is ~1,670 rows;
five of those overlaid is 8,000 points for a chart 700 px wide, which is slower to
draw and no more informative than 120 buckets.
"""

from __future__ import annotations

import statistics
from typing import Optional

BUCKETS = 120
# Below this speed the athlete is standing still and the pace value is meaningless.
MIN_SPEED_MPS = 0.5


def _mean(values: list[float]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return round(statistics.mean(clean), 2) if clean else None


def series_for(activity, buckets: int = BUCKETS) -> dict:
    """Resample one activity onto an even distance grid."""
    records = list(
        activity.records.all()
        .order_by("offset_s")
        .values("offset_s", "distance_m", "speed_mps", "heart_rate",
                "cadence_spm", "altitude_m")
    )
    total = activity.total_distance_m or 0
    if not records or total <= 0:
        return {"id": activity.id, "points": []}

    width = total / buckets
    binned: dict[int, dict[str, list]] = {}
    for r in records:
        distance = r["distance_m"]
        if distance is None:
            continue
        index = min(int(distance / width), buckets - 1)
        slot = binned.setdefault(index, {"pace": [], "hr": [], "cadence": [], "alt": []})
        speed = r["speed_mps"]
        if speed and speed > MIN_SPEED_MPS:
            slot["pace"].append(1000.0 / speed)
        if r["heart_rate"]:
            slot["hr"].append(float(r["heart_rate"]))
        if r["cadence_spm"]:
            slot["cadence"].append(r["cadence_spm"])
        if r["altitude_m"] is not None:
            slot["alt"].append(r["altitude_m"])

    points = []
    for index in range(buckets):
        slot = binned.get(index)
        points.append({
            "km": round((index + 0.5) * width / 1000, 3),
            "pace": _mean(slot["pace"]) if slot else None,
            "hr": _mean(slot["hr"]) if slot else None,
            "cadence": _mean(slot["cadence"]) if slot else None,
            "elevation": _mean(slot["alt"]) if slot else None,
        })

    metrics = getattr(activity, "metrics", None)
    return {
        "id": activity.id,
        "date": activity.local_date,
        "sport": activity.sport,
        "distance_km": round(total / 1000, 2),
        "duration_s": activity.total_elapsed_s,
        "avg_run_pace_s": metrics.avg_run_pace_s_per_km if metrics else None,
        "longest_run_s": metrics.longest_run_s if metrics else None,
        "points": points,
    }
