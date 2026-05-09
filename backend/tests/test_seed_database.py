"""Tests for the SQLite seeder (DATA-01, DATA-04, DATA-05).

Covers:
- DATA-04: ``seed_database.py`` loads the rate table and fuel price
  CSVs into SQLite plus a zones table from JSON.
- DATA-01: the resulting ``rate_table`` has the expected 45 rows and
  schema (shipping types, zones, weight tiers, base_rate_thb).
- DATA-05: the resulting ``zones`` table contains central-1/2/3 with
  non-empty province lists matching ``zone_definitions.json``.

Tests are hermetic: they redirect the seeder's DB_PATH to ``tmp_path``
and never touch the committed ``data/express.db``.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "data" / "scripts"
RAW_DIR = REPO_ROOT / "data" / "raw"
ZONE_JSON = RAW_DIR / "zone_definitions.json"


def _load_seed_module():
    """Load data/scripts/seed_database.py as a fresh module."""
    spec = importlib.util.spec_from_file_location(
        "_seed_database_under_test",
        SCRIPTS_DIR / "seed_database.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def seeded_db(tmp_path, monkeypatch) -> Path:
    """Run ``seed_database.main()`` against a tmp DB and return its path."""
    module = _load_seed_module()
    db_path = tmp_path / "express_test.db"
    # Redirect the seeder's output DB; CSV/JSON inputs stay pointed at
    # the real data/raw/ committed fixtures.
    monkeypatch.setattr(module, "DB_PATH", db_path)
    module.main()
    assert db_path.exists()
    return db_path


class TestSeedDatabaseRateTable:
    """DATA-01 + DATA-04: rate_table is loaded with the right shape."""

    def test_rate_table_has_45_rows(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM rate_table").fetchone()
        assert count == 45

    def test_rate_table_shipping_types(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            rows = conn.execute(
                "SELECT DISTINCT shipping_type FROM rate_table"
            ).fetchall()
        assert {r[0] for r in rows} == {"bounce", "retail_standard", "retail_fast"}

    def test_rate_table_zones(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            rows = conn.execute(
                "SELECT DISTINCT zone FROM rate_table"
            ).fetchall()
        assert {r[0] for r in rows} == {"central-1", "central-2", "central-3"}

    def test_rate_table_weight_tiers(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            rows = conn.execute(
                "SELECT DISTINCT weight_min_kg, weight_max_kg FROM rate_table"
            ).fetchall()
        assert set(rows) == {(0, 5), (5, 10), (10, 20), (20, 50), (50, 999)}

    def test_rate_table_base_rate_range(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            (lo, hi) = conn.execute(
                "SELECT MIN(base_rate_thb), MAX(base_rate_thb) FROM rate_table"
            ).fetchone()
        assert lo >= 50
        assert hi <= 700

    def test_rate_table_full_cross_product(self, seeded_db):
        """Each (type, zone, tier) appears exactly once -> 45 unique combos."""
        with sqlite3.connect(seeded_db) as conn:
            (uniq,) = conn.execute(
                "SELECT COUNT(*) FROM ("
                "  SELECT shipping_type, zone, weight_min_kg, weight_max_kg, "
                "         COUNT(*) AS c "
                "  FROM rate_table "
                "  GROUP BY shipping_type, zone, weight_min_kg, weight_max_kg "
                "  HAVING c = 1"
                ")"
            ).fetchone()
        assert uniq == 45


class TestSeedDatabaseFuelPrices:
    """DATA-04: fuel_prices table is loaded from the seed CSV."""

    def test_fuel_prices_has_at_least_170_rows(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM fuel_prices").fetchone()
        assert count >= 170, f"expected >=170 fuel rows, got {count}"

    def test_fuel_prices_schema(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            cols = [
                row[1]
                for row in conn.execute("PRAGMA table_info(fuel_prices)").fetchall()
            ]
        assert set(cols) == {"date", "diesel_b7_price", "source"}

    def test_fuel_prices_diesel_values_are_realistic(self, seeded_db):
        """Diesel B7 prices should be within a realistic THB/L band.

        Bounds widened to 10-60 in 999.7: P09 monthly aggregates back to
        2003 carry low values (~12.84 in 2003-06) and the April 2026
        post-subsidy spike reached 50.54 baht.
        """
        with sqlite3.connect(seeded_db) as conn:
            (lo, hi) = conn.execute(
                "SELECT MIN(diesel_b7_price), MAX(diesel_b7_price) FROM fuel_prices"
            ).fetchone()
        assert 10.0 <= lo <= 60.0
        assert 10.0 <= hi <= 60.0


class TestSeedDatabaseZones:
    """DATA-05: zones table mirrors zone_definitions.json."""

    def test_zones_has_three_rows(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM zones").fetchone()
        assert count == 3

    def test_zone_ids_match_definitions(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            rows = conn.execute("SELECT zone_id FROM zones").fetchall()
        assert {r[0] for r in rows} == {"central-1", "central-2", "central-3"}

    def test_zone_provinces_loaded_from_json(self, seeded_db):
        """Provinces stored in zones table match the JSON source."""
        expected = json.loads(ZONE_JSON.read_text())
        with sqlite3.connect(seeded_db) as conn:
            rows = conn.execute(
                "SELECT zone_id, name, provinces FROM zones"
            ).fetchall()

        actual = {
            zone_id: {"name": name, "provinces": json.loads(provinces)}
            for zone_id, name, provinces in rows
        }
        assert actual == expected

    def test_each_zone_has_non_empty_province_list(self, seeded_db):
        with sqlite3.connect(seeded_db) as conn:
            rows = conn.execute("SELECT zone_id, provinces FROM zones").fetchall()
        for zone_id, provinces_json in rows:
            provinces = json.loads(provinces_json)
            assert isinstance(provinces, list)
            assert len(provinces) > 0, f"{zone_id} has no provinces"
            assert all(isinstance(p, str) and p for p in provinces)


class TestSeederHelpers:
    """Direct unit coverage for ``seed_rate_table``/``seed_fuel_prices``."""

    def test_seed_rate_table_returns_45(self, tmp_path):
        module = _load_seed_module()
        conn = sqlite3.connect(tmp_path / "x.db")
        try:
            n = module.seed_rate_table(conn)
            assert n == 45
        finally:
            conn.close()

    def test_seed_fuel_prices_returns_at_least_170(self, tmp_path):
        module = _load_seed_module()
        conn = sqlite3.connect(tmp_path / "x.db")
        try:
            n = module.seed_fuel_prices(conn)
            assert n >= 170
        finally:
            conn.close()
