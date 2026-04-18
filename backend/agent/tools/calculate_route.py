"""TOOL-02: calculate_route — Google Maps Directions + zone derivation + TTL cache.

Combines two googlemaps calls per invocation (unless cached):
  1. directions(...) -> distance, duration, duration_in_traffic
  2. geocode(destination) -> province -> zone id via zone_definitions.json

Traffic severity bucketed from duration_in_traffic/duration ratio (D-06).
Results cached in-process for ROUTE_CACHE_TTL_SECONDS (D-07).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import googlemaps

from backend.agent.tools._cache import TTLCache
from backend.agent.tools.models import RouteData
from backend.config import (
    GOOGLE_MAPS_API_KEY,
    ROUTE_CACHE_TTL_SECONDS,
    TRAFFIC_RATIO_BUCKETS,
)

__all__ = ["calculate_route"]

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ZONE_JSON = _REPO_ROOT / "data" / "raw" / "zone_definitions.json"

_route_cache: TTLCache[RouteData] = TTLCache(ttl_seconds=ROUTE_CACHE_TTL_SECONDS)
_gmaps: Optional[googlemaps.Client] = None  # lazy-init so tests can patch


def _client() -> googlemaps.Client:
    """Lazy googlemaps client factory (tests monkeypatch this)."""
    global _gmaps
    if _gmaps is None:
        _gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    return _gmaps


def _normalize_province(name: str) -> str:
    """Strip ' Province' suffix and lowercase (Pitfall 6)."""
    name = name.strip()
    if name.lower().endswith(" province"):
        name = name[: -len(" province")]
    return name.lower()


def _load_zone_index() -> dict[str, str]:
    """Build a normalised province -> zone_id lookup from zone_definitions.json."""
    with open(_ZONE_JSON, encoding="utf-8") as fh:
        zones = json.load(fh)
    index: dict[str, str] = {}
    for zone_id, data in zones.items():
        for province in data.get("provinces", []):
            index[_normalize_province(province)] = zone_id
    return index


_ZONE_INDEX: dict[str, str] = _load_zone_index()


def _bucket_traffic(ratio: float) -> int:
    """Map duration_in_traffic/duration ratio to 1-5 severity (D-06).

    For default TRAFFIC_RATIO_BUCKETS = [1.1, 1.3, 1.5, 1.8]:
        ratio < 1.1 -> 1
        ratio < 1.3 -> 2
        ratio < 1.5 -> 3
        ratio < 1.8 -> 4
        ratio >= 1.8 -> 5
    """
    for level, threshold in enumerate(TRAFFIC_RATIO_BUCKETS, start=1):
        if ratio < threshold:
            return level
    return len(TRAFFIC_RATIO_BUCKETS) + 1  # = 5 for default 4-threshold config


def _zone_for_destination(destination: str) -> str:
    """Reverse-lookup the central-1/2/3 zone for ``destination`` (D-05).

    Raises:
        ValueError: if the destination can't be geocoded or doesn't map to
            a Central Region zone.
    """
    results = _client().geocode(destination)
    if not results:
        raise ValueError(f"Could not geocode destination {destination!r}")
    for comp in results[0].get("address_components", []):
        if "administrative_area_level_1" in comp.get("types", []):
            norm = _normalize_province(comp["long_name"])
            if norm in _ZONE_INDEX:
                return _ZONE_INDEX[norm]
    raise ValueError(f"No Central Region zone for {destination!r}")


def calculate_route(origin: str, destination: str) -> RouteData:
    """Compute route metrics + zone for a (origin, destination) pair.

    Args:
        origin: Address or place string (e.g., "Bangkok").
        destination: Address or place string (e.g., "Nonthaburi").

    Returns:
        RouteData with distance_km, duration_min, traffic_severity (1-5),
        and zone (central-1/2/3).

    Raises:
        ValueError: No route found, or destination outside Central Region.
    """
    key = (origin, destination)
    cached = _route_cache.get(key)
    if cached is not None:
        logger.info("route cache hit: %s -> %s", origin, destination)
        return cached

    client = _client()
    # departure_time + mode=driving required for duration_in_traffic (Pitfall 3)
    results = client.directions(
        origin,
        destination,
        mode="driving",
        departure_time=datetime.now(),
        traffic_model="best_guess",
    )
    if not results:
        raise ValueError(f"No route from {origin!r} to {destination!r}")

    leg = results[0]["legs"][0]
    distance_km = round(leg["distance"]["value"] / 1000.0, 2)
    duration_s = leg["duration"]["value"]
    duration_min = duration_s // 60
    duration_traffic_s = leg.get("duration_in_traffic", {}).get(
        "value", duration_s
    )
    ratio = duration_traffic_s / duration_s if duration_s else 1.0
    severity = _bucket_traffic(ratio)

    zone = _zone_for_destination(destination)

    route = RouteData(
        origin=origin,
        destination=destination,
        distance_km=distance_km,
        duration_min=int(duration_min),
        traffic_severity=severity,
        zone=zone,
    )
    _route_cache.set(key, route)
    logger.info(
        "route computed: %s -> %s (%.1fkm, %dmin, sev=%d, zone=%s)",
        origin, destination, distance_km, duration_min, severity, zone,
    )
    return route
