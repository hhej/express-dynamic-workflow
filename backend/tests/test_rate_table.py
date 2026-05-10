"""Tests for the rate table generator and committed CSV (DATA-01, DATA-03).

Phase 999.9 (D-05/D-06/D-07) — schema migrated to origin_zone × dest_zone:
- 135-row matrix (3 origin × 3 dest × 3 ship × 5 weight)
- Header: shipping_type,origin_zone,dest_zone,weight_min_kg,weight_max_kg,base_rate_thb
- ORIGIN_DEST_MULTIPLIER 3×3 symmetric matrix (diagonal = 1.0 preserves v1.0)

Covers:
- DATA-03: ``data/scripts/generate_rate_table.py`` produces a CSV with
  documented assumptions (3 ship × 3 origin × 3 dest × 5 weight tiers).
- DATA-01: the committed CSV is shaped correctly so seed_database.py
  can load it into SQLite.
- 999.9 D-06: multiplier symmetry + diagonal = 1.0 preservation.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "data" / "scripts"
RAW_DIR = REPO_ROOT / "data" / "raw"
COMMITTED_CSV = RAW_DIR / "express_rate_table.csv"

EXPECTED_SHIPPING_TYPES = {"bounce", "retail_standard", "retail_fast"}
EXPECTED_ZONES = {"central-1", "central-2", "central-3"}
EXPECTED_WEIGHT_TIERS = {(0, 5), (5, 10), (10, 20), (20, 50), (50, 999)}
EXPECTED_COLUMNS = [
    "shipping_type",
    "origin_zone",
    "dest_zone",
    "weight_min_kg",
    "weight_max_kg",
    "base_rate_thb",
]
EXPECTED_ROW_COUNT = 135  # 3 ship × 3 origin × 3 dest × 5 weight


def _load_generate_module():
    """Load data/scripts/generate_rate_table.py without polluting sys.path."""
    spec = importlib.util.spec_from_file_location(
        "_generate_rate_table_under_test",
        SCRIPTS_DIR / "generate_rate_table.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def generated_csv(tmp_path, monkeypatch) -> Path:
    """Run ``generate_rate_table.main()`` against a tmp output and return
    the path to the freshly written CSV.
    """
    fake_scripts = tmp_path / "scripts"
    fake_raw = tmp_path / "raw"
    fake_scripts.mkdir()
    fake_raw.mkdir()

    module = _load_generate_module()
    monkeypatch.setattr(
        module, "__file__", str(fake_scripts / "generate_rate_table.py")
    )
    module.main()

    out = fake_raw / "express_rate_table.csv"
    assert out.exists(), "generate_rate_table.main() did not produce a CSV"
    return out


class TestGenerateRateTable:
    """DATA-03 + 999.9 D-05: generator produces 135 rows with new matrix."""

    def test_generated_csv_has_expected_schema(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert list(df.columns) == EXPECTED_COLUMNS

    def test_generated_csv_has_135_rows(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert len(df) == EXPECTED_ROW_COUNT, (
            f"expected 3*3*3*5=135 rows, got {len(df)}"
        )

    def test_generated_csv_covers_all_shipping_types(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert set(df["shipping_type"].unique()) == EXPECTED_SHIPPING_TYPES

    def test_generated_csv_covers_all_origin_zones(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert set(df["origin_zone"].unique()) == EXPECTED_ZONES

    def test_generated_csv_covers_all_dest_zones(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert set(df["dest_zone"].unique()) == EXPECTED_ZONES

    def test_generated_csv_covers_all_weight_tiers(self, generated_csv):
        df = pd.read_csv(generated_csv)
        tiers = {
            (int(row.weight_min_kg), int(row.weight_max_kg))
            for row in df.itertuples()
        }
        assert tiers == EXPECTED_WEIGHT_TIERS

    def test_generated_csv_full_cross_product(self, generated_csv):
        """Every (ship, origin, dest, weight_tier) combo appears exactly once."""
        df = pd.read_csv(generated_csv)
        combos = df.groupby(
            [
                "shipping_type",
                "origin_zone",
                "dest_zone",
                "weight_min_kg",
                "weight_max_kg",
            ]
        ).size()
        assert (combos == 1).all()
        assert len(combos) == EXPECTED_ROW_COUNT

    def test_generated_csv_rate_range(self, generated_csv):
        """Base rates fall in 50-800 THB band (1.7x cross-zone bumps top end)."""
        df = pd.read_csv(generated_csv)
        assert df["base_rate_thb"].min() >= 50
        # 50 (retail_standard 0-5 c1->c1) to 765 (retail_fast 50+ c1->c3)
        assert df["base_rate_thb"].max() <= 800

    def test_dest_zone_multiplier_monotonic_per_origin(self, generated_csv):
        """For each (ship, origin, weight_tier), dest=origin (diagonal) is the
        cheapest; off-diagonal dest_zones cost more or equal.

        Replaces the v1.0 monotonic central-1 < central-2 < central-3 check —
        D-06 symmetric matrix means central-3 origin pays the same to ship to
        central-1 as a central-1 origin pays to ship to central-3.
        """
        df = pd.read_csv(generated_csv)
        for (st, origin, wmin, wmax), group in df.groupby(
            ["shipping_type", "origin_zone", "weight_min_kg", "weight_max_kg"]
        ):
            by_dest = dict(zip(group["dest_zone"], group["base_rate_thb"]))
            diag = by_dest[origin]
            for dest_zone, rate in by_dest.items():
                if dest_zone == origin:
                    continue
                assert rate >= diag, (
                    f"diagonal not cheapest for {st} from {origin} weight "
                    f"{wmin}-{wmax}: {origin}->{dest_zone}={rate} < "
                    f"{origin}->{origin}={diag}"
                )

    def test_documented_assumptions_in_module_docstring(self):
        """DATA-03 acceptance: docstring records the 999.9 modelling assumption."""
        module = _load_generate_module()
        assert module.__doc__ is not None
        assert "ORIGIN_DEST_MULTIPLIER" in module.__doc__


class TestCommittedRateTableCsv:
    """DATA-01: the CSV checked into data/raw/ is what seed_database.py
    feeds into SQLite. Validate it independently of regenerating it.
    """

    def test_committed_csv_exists(self):
        assert COMMITTED_CSV.exists(), (
            f"committed rate table CSV missing at {COMMITTED_CSV}"
        )

    def test_committed_csv_schema_and_size(self):
        df = pd.read_csv(COMMITTED_CSV)
        assert list(df.columns) == EXPECTED_COLUMNS
        assert len(df) == EXPECTED_ROW_COUNT

    def test_committed_csv_value_domains(self):
        df = pd.read_csv(COMMITTED_CSV)
        assert set(df["shipping_type"].unique()) == EXPECTED_SHIPPING_TYPES
        assert set(df["origin_zone"].unique()) == EXPECTED_ZONES
        assert set(df["dest_zone"].unique()) == EXPECTED_ZONES
        tiers = {
            (int(row.weight_min_kg), int(row.weight_max_kg))
            for row in df.itertuples()
        }
        assert tiers == EXPECTED_WEIGHT_TIERS
        assert df["base_rate_thb"].between(50, 800).all()


# --- Phase 999.9 D-06 / Wave 1 Plan 01 Task 2 NEW tests ---


class TestPhase999_9Schema:
    """Phase 999.9 D-05/D-06/D-07: 135-row matrix + symmetry + v1.0 preservation."""

    def test_135_rows_after_regeneration(self):
        """D-05: committed CSV has 135 data rows after Wave 1 regeneration."""
        df = pd.read_csv(COMMITTED_CSV)
        assert len(df) == 135

    def test_diagonal_preserves_v1_central1_rates(self):
        """Pitfall 3: M[c-1][c-1] = 1.0 means central-1 → central-1 rates
        match v1.0 base rates byte-for-byte."""
        df = pd.read_csv(COMMITTED_CSV)
        diag = df[
            (df["origin_zone"] == "central-1")
            & (df["dest_zone"] == "central-1")
            & (df["weight_min_kg"] == 0)
            & (df["weight_max_kg"] == 5)
        ]
        rates = dict(zip(diag["shipping_type"], diag["base_rate_thb"]))
        assert rates["bounce"] == 55, f"bounce 0-5 c1->c1: {rates['bounce']}"
        assert rates["retail_standard"] == 50, (
            f"retail_standard 0-5 c1->c1: {rates['retail_standard']}"
        )
        assert rates["retail_fast"] == 65, (
            f"retail_fast 0-5 c1->c1: {rates['retail_fast']}"
        )

    def test_multiplier_symmetry(self):
        """D-06: rate(origin=A, dest=B) == rate(origin=B, dest=A) for all
        (shipping_type, weight_tier) combos."""
        df = pd.read_csv(COMMITTED_CSV)
        for st in EXPECTED_SHIPPING_TYPES:
            for wmin, wmax in EXPECTED_WEIGHT_TIERS:
                rows = df[
                    (df["shipping_type"] == st)
                    & (df["weight_min_kg"] == wmin)
                    & (df["weight_max_kg"] == wmax)
                ]
                lookup = {
                    (r.origin_zone, r.dest_zone): r.base_rate_thb
                    for r in rows.itertuples()
                }
                for a, b in [
                    ("central-1", "central-2"),
                    ("central-1", "central-3"),
                    ("central-2", "central-3"),
                ]:
                    assert lookup[(a, b)] == lookup[(b, a)], (
                        f"asymmetry for {st} {wmin}-{wmax}: "
                        f"{a}->{b}={lookup[(a, b)]} vs "
                        f"{b}->{a}={lookup[(b, a)]}"
                    )

    def test_origin_zone_column_before_dest_zone(self):
        """D-07: CSV header has origin_zone BEFORE dest_zone."""
        with open(COMMITTED_CSV, encoding="utf-8") as fh:
            first_line = fh.readline().rstrip("\n")
        assert first_line.startswith(
            "shipping_type,origin_zone,dest_zone,"
        ), f"header order wrong: {first_line!r}"

    def test_origin_dest_multiplier_values(self):
        """D-06: multiplier matrix values match the documented calibration."""
        module = _load_generate_module()
        m = module.ORIGIN_DEST_MULTIPLIER
        assert m["central-1"]["central-1"] == 1.00
        assert m["central-1"]["central-2"] == 1.25
        assert m["central-1"]["central-3"] == 1.70
        assert m["central-2"]["central-1"] == 1.25
        assert m["central-2"]["central-2"] == 1.00
        assert m["central-2"]["central-3"] == 1.45
        assert m["central-3"]["central-1"] == 1.70
        assert m["central-3"]["central-2"] == 1.45
        assert m["central-3"]["central-3"] == 1.00

    def test_no_zone_multipliers_constant_remains(self):
        """Pitfall 3: legacy ZONE_MULTIPLIERS dict must be removed entirely
        — leaving it would invite double-multiplication bugs."""
        module = _load_generate_module()
        assert not hasattr(module, "ZONE_MULTIPLIERS"), (
            "Legacy ZONE_MULTIPLIERS still present in generate_rate_table.py"
        )
