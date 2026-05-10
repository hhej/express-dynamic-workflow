"""Phase 999.9 (D-01..D-04): hub_id -> {name, address, zone} loader.

Mirrors the _ZONE_INDEX pattern in calculate_route.py — single load
at module import time, no runtime invalidation. Restart uvicorn to
pick up hubs.json edits.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

__all__ = [
    "_load_hub_index",
    "_HUB_INDEX",
    "origin_string_for",
    "origin_zone_for",
    "hub_label_for",
]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HUBS_JSON = _REPO_ROOT / "data" / "raw" / "hubs.json"


def _load_hub_index() -> Dict[str, dict]:
    """hub_id -> {name, address, zone}. Built once at import time.

    Returns:
        Dict keyed by hub_id (e.g., 'hq-lat-krabang') with the full
        hub object as value.
    """
    with open(_HUBS_JSON, encoding="utf-8") as fh:
        return json.load(fh)


_HUB_INDEX: Dict[str, dict] = _load_hub_index()


def origin_string_for(hub_id: str) -> str:
    """Resolve hub_id to the address googlemaps geocodes (D-04).

    Args:
        hub_id: One of the 10 known hub identifiers (e.g., 'hq-lat-krabang').

    Returns:
        The hub's address string ready for googlemaps.directions / geocode.

    Raises:
        ValueError: If hub_id is not in the loaded hub index.
    """
    hub = _HUB_INDEX.get(hub_id)
    if not hub:
        raise ValueError(
            f"unknown hub_id={hub_id!r}; allowed={sorted(_HUB_INDEX)}"
        )
    return hub["address"]


def hub_label_for(hub_id: str) -> str:
    """Narration-friendly hub label (Phase 999.9 narration coherence).

    Returns the part after ' — ' in ``hub.name`` (e.g.,
    'Phra Nakhon Si Ayutthaya' from 'Express Branch — Phra Nakhon Si
    Ayutthaya'), falling back to the full name if the em-dash separator
    is absent.

    Args:
        hub_id: One of the 10 known hub identifiers.

    Returns:
        Short, narration-ready label suitable for both the seed bullets
        the Pricing Agent emits and the prose summary the Response Node
        renders into the chat answer.

    Raises:
        ValueError: If hub_id is not in the loaded hub index.
    """
    hub = _HUB_INDEX.get(hub_id)
    if not hub:
        raise ValueError(
            f"unknown hub_id={hub_id!r}; allowed={sorted(_HUB_INDEX)}"
        )
    name = hub["name"]
    return name.split(" — ", 1)[-1] if " — " in name else name


def origin_zone_for(hub_id: str) -> str:
    """Resolve hub_id to its zone (D-05 lookup_rate input).

    Args:
        hub_id: One of the 10 known hub identifiers.

    Returns:
        The hub's zone id ('central-1' | 'central-2' | 'central-3').

    Raises:
        ValueError: If hub_id is not in the loaded hub index.
    """
    hub = _HUB_INDEX.get(hub_id)
    if not hub:
        raise ValueError(
            f"unknown hub_id={hub_id!r}; allowed={sorted(_HUB_INDEX)}"
        )
    return hub["zone"]
