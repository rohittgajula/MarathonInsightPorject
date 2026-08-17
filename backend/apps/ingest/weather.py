"""Weather at the time and place of each run.

Heat is the single most under-attributed cause of a bad session. Without it the app
would blame poor sleep or lost fitness for a run that was simply 32 C — and would
then ease a plan that never needed easing.

Open-Meteo's archive endpoint is used because it needs no key and no account, which
keeps this working for anyone who clones the project. Values are fetched once per
activity and stored: the weather on 17 August will not change, so re-fetching it is
pure waste and an avoidable dependency on someone else's uptime.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen
import json

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 20

# Above roughly this, heat starts measurably costing pace for an unacclimatised
# runner. Humidity matters more than raw temperature, which is why apparent
# temperature is what gets judged.
HEAT_THRESHOLD_C = 24.0


def _fetch(url: str, params: dict) -> Optional[dict]:
    try:
        with urlopen(f"{url}?{urlencode(params)}", timeout=TIMEOUT_S) as response:
            return json.loads(response.read().decode())
    except Exception as exc:  # noqa: BLE001 — weather is context, never load-bearing
        logger.warning("weather lookup failed: %s", exc)
        return None


def for_activity(activity) -> dict:
    """Conditions at the start of one activity. Empty dict when unavailable."""
    first = (
        activity.records.exclude(latitude__isnull=True)
        .order_by("offset_s")
        .values("latitude", "longitude")
        .first()
    )
    if not first or activity.started_at is None:
        return {}

    started = activity.started_at
    day = started.date()
    # The archive lags a few days behind; recent runs come from the forecast endpoint,
    # which also serves the recent past.
    recent = (dt.date.today() - day).days < 6
    payload = _fetch(FORECAST_URL if recent else ARCHIVE_URL, {
        "latitude": round(first["latitude"], 3),
        "longitude": round(first["longitude"], 3),
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,apparent_temperature",
        "timezone": "UTC",
    })
    hourly = (payload or {}).get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return {}

    # Match the hour the run started, in UTC.
    target = started.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:00")
    index = times.index(target) if target in times else min(started.hour, len(times) - 1)

    def at(key):
        values = hourly.get(key) or []
        return values[index] if index < len(values) else None

    return {
        "temp_c": at("temperature_2m"),
        "feels_like_c": at("apparent_temperature"),
        "humidity_pct": at("relative_humidity_2m"),
        "wind_kmh": at("wind_speed_10m"),
    }


def heat_penalty_s_per_km(feels_like_c: Optional[float]) -> Optional[int]:
    """Rough pace cost of heat, in seconds per km.

    Deliberately conservative and rounded. The published figures vary widely by
    acclimatisation and humidity, so this is presented as an estimate and never used
    to adjust training — only to stop the athlete reading a hot day as lost fitness.
    """
    if feels_like_c is None or feels_like_c <= HEAT_THRESHOLD_C:
        return None
    over = feels_like_c - HEAT_THRESHOLD_C
    return int(min(round(over * 3.5), 90))


def backfill(athlete, limit: int = 50) -> dict:
    """Fill in weather for activities that do not have it yet."""
    from apps.activities.models import Activity

    pending = Activity.objects.filter(
        athlete=athlete, weather_checked=False
    ).order_by("-started_at")[:limit]

    filled = 0
    for activity in pending:
        data = for_activity(activity)
        point = (
            activity.records.exclude(latitude__isnull=True)
            .values("latitude", "longitude").first()
        )
        if point and not activity.place_name:
            activity.place_name = place_name(point["latitude"], point["longitude"])
        # Marked checked either way, so a run with no GPS is not retried forever.
        activity.weather_checked = True
        for key, value in data.items():
            setattr(activity, key, value)
        activity.save(update_fields=[
            "weather_checked", "temp_c", "feels_like_c", "humidity_pct", "wind_kmh",
            "place_name",
        ])
        if data:
            filled += 1
    return {"checked": len(pending), "filled": filled}


# WMO weather codes, grouped to what a runner actually needs to know.
WMO = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Freezing fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow",
    80: "Rain showers", 81: "Rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with hail",
}


def _last_known_location(athlete):
    from apps.activities.models import Activity

    activity = (
        Activity.objects.filter(athlete=athlete)
        .exclude(records__latitude__isnull=True)
        .order_by("-started_at")
        .first()
    )
    if activity is None:
        return None
    point = (
        activity.records.exclude(latitude__isnull=True)
        .values("latitude", "longitude").first()
    )
    return point


def forecast(athlete, day, hour: int = 6) -> dict:
    """Conditions expected for a session, with the precautions that follow.

    Cached for three hours: the forecast for tomorrow morning does not move minute to
    minute, and the dashboard is loaded often enough that re-fetching would be both
    slow and rude to a free service.
    """
    from django.core.cache import cache

    point = _last_known_location(athlete)
    if point is None:
        return {}

    key = f"forecast:{athlete.pk}:{day.isoformat()}:{hour}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    payload = _fetch(FORECAST_URL, {
        "latitude": round(point["latitude"], 3),
        "longitude": round(point["longitude"], 3),
        "hourly": ("temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "wind_speed_10m,precipitation_probability,weather_code"),
        "forecast_days": 4,
        "timezone": athlete.timezone or "UTC",
    })
    hourly = (payload or {}).get("hourly") or {}
    times = hourly.get("time") or []
    target = f"{day.isoformat()}T{hour:02d}:00"
    if target not in times:
        return {}
    i = times.index(target)

    def at(key_name):
        values = hourly.get(key_name) or []
        return values[i] if i < len(values) else None

    result = {
        "date": day, "hour": hour,
        "place": place_name(point["latitude"], point["longitude"]),
        "temp_c": at("temperature_2m"),
        "feels_like_c": at("apparent_temperature"),
        "humidity_pct": at("relative_humidity_2m"),
        "wind_kmh": at("wind_speed_10m"),
        "rain_chance_pct": at("precipitation_probability"),
        "conditions": WMO.get(at("weather_code"), ""),
    }
    result["advice"] = advice_for(result)
    cache.set(key, result, 60 * 60 * 3)
    return result


def advice_for(conditions: dict) -> list[dict]:
    """Precautions that follow from the forecast.

    Heat advice leads with the pace consequence rather than a warning, because the
    failure mode is not heatstroke — it is running the prescribed pace in 30 C, finding
    it brutal, and concluding fitness has gone backwards.
    """
    out: list[dict] = []
    feels = conditions.get("feels_like_c")
    humidity = conditions.get("humidity_pct") or 0
    wind = conditions.get("wind_kmh") or 0
    rain = conditions.get("rain_chance_pct") or 0
    label = (conditions.get("conditions") or "").lower()

    penalty = heat_penalty_s_per_km(feels)
    if feels is not None and feels >= 32:
        out.append({"tone": "warn", "title": f"Serious heat — feels like {feels:.0f} C",
                    "detail": (f"Expect roughly {penalty} s/km slower for the same effort. Run by "
                               "heart rate today and ignore the pace target entirely. Go earlier "
                               "if you can, carry water, and cut the session short rather than "
                               "pushing through.")})
    elif penalty:
        out.append({"tone": "warn", "title": f"Warm — feels like {feels:.0f} C",
                    "detail": (f"Expect around {penalty} s/km slower for the same effort. That is "
                               "the heat, not lost fitness — hold your heart rate and let the pace "
                               "be what it is.")})

    if humidity >= 80:
        out.append({"tone": "warn", "title": f"Humidity {humidity:.0f}%",
                    "detail": ("Sweat cannot evaporate, so cooling barely works and heart rate runs "
                               "high for the same pace. Take the walk breaks early.")})

    if rain >= 50:
        out.append({"tone": "neutral", "title": f"{rain:.0f}% chance of rain",
                    "detail": ("Rain itself is fine to run in and often feels easier than heat. "
                               "Watch footing on painted lines and metal covers, and put your "
                               "phone somewhere dry.")})
    if "thunder" in label:
        out.append({"tone": "warn", "title": "Thunderstorms forecast",
                    "detail": "Do not run through lightning. Move the session indoors or to another day."})

    if wind >= 25:
        out.append({"tone": "neutral", "title": f"Windy — {wind:.0f} km/h",
                    "detail": ("Head out into the wind and come back with it. Into a headwind, hold "
                               "the effort and accept the slower pace.")})

    if feels is not None and feels <= 10:
        out.append({"tone": "neutral", "title": f"Cold — feels like {feels:.0f} C",
                    "detail": "Layer up for the first kilometre, and warm up indoors before starting."})

    if not out:
        out.append({"tone": "good", "title": "Good conditions",
                    "detail": "Nothing in the weather to work around. Run the session as written."})
    return out


NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
# Nominatim requires an identifying User-Agent and asks for at most one request per
# second. Place names never change, so every lookup is cached hard and stored on the
# activity — in practice this hits the network once per new location, not per page view.
USER_AGENT = "RunProject/0.1 (self-hosted personal training app)"
PLACE_CACHE_S = 60 * 60 * 24 * 30


def place_name(latitude: float, longitude: float) -> str:
    """A human place name for coordinates, e.g. 'Kannala, Telangana'."""
    from urllib.request import Request

    from django.core.cache import cache

    # Rounding to ~1 km also means nearby runs share one cache entry and one request.
    key = f"place:{round(latitude, 2)}:{round(longitude, 2)}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    params = urlencode({
        "lat": round(latitude, 4), "lon": round(longitude, 4),
        "format": "json", "zoom": 14, "addressdetails": 1,
    })
    try:
        request = Request(f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=TIMEOUT_S) as response:
            payload = json.loads(response.read().decode())
    except Exception as exc:  # noqa: BLE001 — a missing name is cosmetic
        logger.warning("reverse geocode failed: %s", exc)
        return ""

    address = payload.get("address") or {}
    locality = next(
        (address[k] for k in ("suburb", "village", "town", "city", "hamlet", "neighbourhood")
         if address.get(k)), "")
    region = next((address[k] for k in ("state", "county") if address.get(k)), "")
    name = ", ".join(part for part in (locality, region) if part)

    if name:
        cache.set(key, name, PLACE_CACHE_S)
    return name


def location_for(athlete) -> dict:
    """Where the athlete last ran, named."""
    point = _last_known_location(athlete)
    if not point:
        return {}
    return {
        "latitude": point["latitude"],
        "longitude": point["longitude"],
        "name": place_name(point["latitude"], point["longitude"]),
    }
