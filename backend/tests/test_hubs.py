"""Phase 999.9 D-01..D-04 tests for hubs.json shape + helper module.

Covers:
- D-01 (hubs.json shape: 10 entries, required keys per hub)
- D-02 (zone distribution: central-1=5, central-2=3, central-3=2)
- D-03 (10 hub_ids verbatim)
- D-04 (origin_string_for, origin_zone_for helpers + unknown-id errors)
"""
from __future__ import annotations

import pytest

from backend.agent.tools.hubs import (
    _HUB_INDEX,
    _load_hub_index,
    origin_string_for,
    origin_zone_for,
)


EXPECTED_HUB_IDS = {
    "hq-lat-krabang",
    "branch-bang-na",
    "branch-nonthaburi",
    "branch-pathum-thani",
    "branch-samut-prakan",
    "branch-ayutthaya",
    "branch-nakhon-pathom",
    "branch-samut-sakhon",
    "branch-ratchaburi",
    "branch-lop-buri",
}


def test_load_hubs_returns_10_entries():
    """D-01: hubs.json has exactly 10 top-level keys (1 HQ + 9 branches)."""
    hubs = _load_hub_index()
    assert len(hubs) == 10


def test_zone_distribution():
    """D-02: zone distribution is central-1=5, central-2=3, central-3=2."""
    central_1 = sum(1 for v in _HUB_INDEX.values() if v["zone"] == "central-1")
    central_2 = sum(1 for v in _HUB_INDEX.values() if v["zone"] == "central-2")
    central_3 = sum(1 for v in _HUB_INDEX.values() if v["zone"] == "central-3")
    assert central_1 == 5, f"expected 5 central-1 hubs, got {central_1}"
    assert central_2 == 3, f"expected 3 central-2 hubs, got {central_2}"
    assert central_3 == 2, f"expected 2 central-3 hubs, got {central_3}"


def test_all_expected_hub_ids_present():
    """D-03: the 10 hub_ids exactly match the verbatim list from CONTEXT."""
    assert set(_HUB_INDEX.keys()) == EXPECTED_HUB_IDS


def test_origin_string_for_known_hub():
    """D-04: origin_string_for resolves hub_id to the address string."""
    assert (
        origin_string_for("hq-lat-krabang")
        == "Lat Krabang Industrial Estate, Bangkok"
    )


def test_origin_zone_for_known_hub():
    """D-04: origin_zone_for resolves hub_id to its zone id."""
    assert origin_zone_for("hq-lat-krabang") == "central-1"
    assert origin_zone_for("branch-ayutthaya") == "central-2"
    assert origin_zone_for("branch-lop-buri") == "central-3"


def test_unknown_hub_id_raises_value_error():
    """D-04: both helpers raise ValueError on unknown hub_id."""
    with pytest.raises(ValueError, match="unknown hub_id"):
        origin_string_for("nonexistent")
    with pytest.raises(ValueError, match="unknown hub_id"):
        origin_zone_for("nonexistent")


def test_required_keys_per_hub():
    """D-01: every hub object has exactly the keys: name, address, zone."""
    for hub_id, hub in _HUB_INDEX.items():
        assert set(hub.keys()) == {"name", "address", "zone"}, (
            f"{hub_id} has unexpected keys: {sorted(hub.keys())}"
        )
