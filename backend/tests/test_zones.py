"""Tests for ``data/raw/zone_definitions.json`` (DATA-05).

The seeder copies these definitions into the ``zones`` table; this
file pins down the JSON contract independently so a malformed edit
to the source fails fast.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ZONE_JSON = REPO_ROOT / "data" / "raw" / "zone_definitions.json"

EXPECTED_ZONE_IDS = {"central-1", "central-2", "central-3"}


@pytest.fixture(scope="module")
def zones() -> dict:
    return json.loads(ZONE_JSON.read_text(encoding="utf-8"))


def test_zone_definitions_file_exists():
    assert ZONE_JSON.exists(), f"missing zone definitions at {ZONE_JSON}"


def test_zone_definitions_top_level_keys(zones):
    assert set(zones.keys()) == EXPECTED_ZONE_IDS


@pytest.mark.parametrize("zone_id", sorted(EXPECTED_ZONE_IDS))
def test_zone_has_name_and_provinces(zones, zone_id):
    entry = zones[zone_id]
    assert isinstance(entry, dict)
    assert "name" in entry and isinstance(entry["name"], str) and entry["name"].strip()
    assert "provinces" in entry and isinstance(entry["provinces"], list)
    assert len(entry["provinces"]) > 0
    assert all(isinstance(p, str) and p.strip() for p in entry["provinces"])


def test_central_1_includes_bangkok(zones):
    """Domain check: central-1 = Bangkok Metro must include Bangkok itself."""
    assert "Bangkok" in zones["central-1"]["provinces"]


def test_no_duplicate_provinces_across_zones(zones):
    """A province belongs to exactly one zone (no overlap)."""
    seen: set[str] = set()
    for zone_id, entry in zones.items():
        for province in entry["provinces"]:
            assert province not in seen, (
                f"province {province!r} appears in multiple zones"
            )
            seen.add(province)
