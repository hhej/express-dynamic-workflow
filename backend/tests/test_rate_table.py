"""Tests for the rate table generator and committed CSV (DATA-01, DATA-03).

Covers:
- DATA-03: ``data/scripts/generate_rate_table.py`` produces a CSV with
  documented assumptions (3 shipping types x 3 zones x 5 weight tiers).
- DATA-01: the committed CSV is shaped correctly so seed_database.py
  can load it into SQLite (45 rate rows of the right schema and value
  ranges). The end-to-end DB seed is exercised in test_seed_database.py.
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
    "zone",
    "weight_min_kg",
    "weight_max_kg",
    "base_rate_thb",
]


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

    Patches ``Path.__file__`` indirectly by changing the module's path
    resolution: we rely on the script writing to
    ``Path(__file__).parent.parent / "raw" / "express_rate_table.csv"``,
    so we mirror that layout under tmp_path and patch the module's
    ``__file__`` attribute.
    """
    fake_scripts = tmp_path / "scripts"
    fake_raw = tmp_path / "raw"
    fake_scripts.mkdir()
    fake_raw.mkdir()

    module = _load_generate_module()
    # Point the module's __file__ at our tmp scripts dir so the
    # `Path(__file__).parent.parent / "raw" / ...` resolution lands inside tmp.
    monkeypatch.setattr(module, "__file__", str(fake_scripts / "generate_rate_table.py"))
    module.main()

    out = fake_raw / "express_rate_table.csv"
    assert out.exists(), "generate_rate_table.main() did not produce a CSV"
    return out


class TestGenerateRateTable:
    """DATA-03: generator produces 45 rows with the documented matrix."""

    def test_generated_csv_has_expected_schema(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert list(df.columns) == EXPECTED_COLUMNS

    def test_generated_csv_has_45_rows(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert len(df) == 45, f"expected 3*3*5=45 rows, got {len(df)}"

    def test_generated_csv_covers_all_shipping_types(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert set(df["shipping_type"].unique()) == EXPECTED_SHIPPING_TYPES

    def test_generated_csv_covers_all_zones(self, generated_csv):
        df = pd.read_csv(generated_csv)
        assert set(df["zone"].unique()) == EXPECTED_ZONES

    def test_generated_csv_covers_all_weight_tiers(self, generated_csv):
        df = pd.read_csv(generated_csv)
        tiers = {
            (int(row.weight_min_kg), int(row.weight_max_kg))
            for row in df.itertuples()
        }
        assert tiers == EXPECTED_WEIGHT_TIERS

    def test_generated_csv_full_cross_product(self, generated_csv):
        """Every (shipping_type, zone, weight_tier) combo appears exactly once."""
        df = pd.read_csv(generated_csv)
        combos = df.groupby(
            ["shipping_type", "zone", "weight_min_kg", "weight_max_kg"]
        ).size()
        assert (combos == 1).all()
        assert len(combos) == 45

    def test_generated_csv_rate_range(self, generated_csv):
        """Base rates fall in the documented 50-700 THB band (D-02)."""
        df = pd.read_csv(generated_csv)
        assert df["base_rate_thb"].min() >= 50
        assert df["base_rate_thb"].max() <= 700

    def test_zone_multiplier_monotonic_per_tier(self, generated_csv):
        """central-1 < central-2 < central-3 for each (shipping_type, weight_tier)."""
        df = pd.read_csv(generated_csv)
        for (st, wmin, wmax), group in df.groupby(
            ["shipping_type", "weight_min_kg", "weight_max_kg"]
        ):
            by_zone = dict(zip(group["zone"], group["base_rate_thb"]))
            c1, c2, c3 = by_zone["central-1"], by_zone["central-2"], by_zone["central-3"]
            assert c1 < c2 < c3, (
                f"zone multiplier broken for {st} {wmin}-{wmax}: "
                f"c1={c1} c2={c2} c3={c3}"
            )

    def test_documented_assumptions_in_module_docstring(self):
        """DATA-03 acceptance: docstring records the modelling assumption."""
        module = _load_generate_module()
        assert module.__doc__ is not None
        assert "Base rates modeled on Thai Express" in module.__doc__


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
        assert len(df) == 45

    def test_committed_csv_value_domains(self):
        df = pd.read_csv(COMMITTED_CSV)
        assert set(df["shipping_type"].unique()) == EXPECTED_SHIPPING_TYPES
        assert set(df["zone"].unique()) == EXPECTED_ZONES
        tiers = {
            (int(row.weight_min_kg), int(row.weight_max_kg))
            for row in df.itertuples()
        }
        assert tiers == EXPECTED_WEIGHT_TIERS
        assert df["base_rate_thb"].between(50, 700).all()
