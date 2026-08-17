"""FIT decoding.

The FIT file carries far more than the Garmin Connect summary: today's 28-minute
sample activity returns a 2-lap summary from the API but contains 1,670 per-second
records in the file. The per-second series is the only thing that makes run/walk
segmentation possible, so parsing happens from the file, never from the API summary.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

from fitparse import FitFile

from apps.analysis.segmentation import Sample

SEMICIRCLE_TO_DEGREES = 180.0 / 2**31


@dataclass
class ParsedActivity:
    sport: str = "running"
    started_at: Optional[dt.datetime] = None
    total_distance_m: float = 0.0
    total_timer_s: float = 0.0
    total_elapsed_s: float = 0.0
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_cadence_spm: Optional[float] = None
    total_ascent_m: Optional[float] = None
    total_descent_m: Optional[float] = None
    calories: Optional[int] = None
    samples: list[Sample] = field(default_factory=list)


def _val(msg, name) -> Any:
    field_data = msg.get(name)
    return field_data.value if field_data else None


def _full_cadence(record: dict) -> Optional[float]:
    """FIT stores running cadence per-leg; double it for true steps/min.

    `fractional_cadence` carries the half-step, so a 84.5 rpm reading is 169 spm.
    """
    cadence = record.get("cadence")
    if cadence is None:
        return None
    return (cadence + (record.get("fractional_cadence") or 0.0)) * 2


def parse(path_or_fileobj) -> ParsedActivity:
    fit = FitFile(path_or_fileobj)
    parsed = ParsedActivity()

    for session in fit.get_messages("session"):
        parsed.sport = _val(session, "sport") or "running"
        parsed.started_at = _val(session, "start_time")
        parsed.total_distance_m = _val(session, "total_distance") or 0.0
        parsed.total_timer_s = _val(session, "total_timer_time") or 0.0
        parsed.total_elapsed_s = _val(session, "total_elapsed_time") or 0.0
        parsed.avg_hr = _val(session, "avg_heart_rate")
        parsed.max_hr = _val(session, "max_heart_rate")
        parsed.total_ascent_m = _val(session, "total_ascent")
        parsed.total_descent_m = _val(session, "total_descent")
        parsed.calories = _val(session, "total_calories")
        avg_cadence = _val(session, "avg_running_cadence")
        if avg_cadence:
            parsed.avg_cadence_spm = avg_cadence * 2
        break

    raw_records = []
    for record in fit.get_messages("record"):
        raw_records.append({d.name: d.value for d in record})

    if not raw_records:
        return parsed

    first_ts = raw_records[0].get("timestamp")
    if parsed.started_at is None:
        parsed.started_at = first_ts

    for record in raw_records:
        timestamp = record.get("timestamp")
        if timestamp is None or first_ts is None:
            continue

        lat = record.get("position_lat")
        lon = record.get("position_long")

        parsed.samples.append(
            Sample(
                offset_s=(timestamp - first_ts).total_seconds(),
                distance_m=record.get("distance"),
                speed_mps=record.get("enhanced_speed") or record.get("speed"),
                cadence_spm=_full_cadence(record),
                heart_rate=record.get("heart_rate"),
            )
        )
        # Coordinates are kept on the model but not on Sample, which stays minimal for
        # the segmentation hot path; they are re-read from raw_records at persist time.
        parsed.samples[-1].__dict__["_lat"] = lat * SEMICIRCLE_TO_DEGREES if lat else None
        parsed.samples[-1].__dict__["_lon"] = lon * SEMICIRCLE_TO_DEGREES if lon else None
        parsed.samples[-1].__dict__["_alt"] = record.get("enhanced_altitude") or record.get("altitude")
        # Running dynamics ride along on the Sample without entering the segmentation
        # hot path, which stays deliberately narrow.
        parsed.samples[-1].__dict__["_dyn"] = {
            "power_w": record.get("power"),
            "vertical_oscillation_mm": record.get("vertical_oscillation"),
            "ground_contact_ms": record.get("stance_time"),
            "stride_length_m": record.get("step_length") / 1000.0
                               if record.get("step_length") else None,
            "vertical_ratio": record.get("vertical_ratio"),
            "respiration_rate": record.get("respiration_rate")
                                or record.get("enhanced_respiration_rate"),
            "temperature_c": record.get("temperature"),
        }

    if parsed.total_distance_m == 0.0 and parsed.samples:
        distances = [s.distance_m for s in parsed.samples if s.distance_m is not None]
        if distances:
            parsed.total_distance_m = max(distances)

    if parsed.total_elapsed_s == 0.0 and parsed.samples:
        parsed.total_elapsed_s = parsed.samples[-1].offset_s

    return parsed
