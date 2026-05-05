"""Tests for the EPPO fuel-price fetcher with seed-CSV fallback (DATA-02).

The script's contract (per 01-01-PLAN, D-05..D-08):
- Attempts to scrape EPPO via ``_scrape_eppo``.
- On ANY failure, falls back to the committed seed CSV.
- Either way, ``main()`` exits cleanly and the seed CSV remains a
  valid ``date,diesel_b7_price,source`` table with >=170 rows.

We never hit the live network here; all paths are exercised via
``monkeypatch`` against ``_scrape_eppo`` and ``requests.get``.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "data" / "scripts"
RAW_DIR = REPO_ROOT / "data" / "raw"
SEED_CSV = RAW_DIR / "eppo_diesel_prices.csv"

EXPECTED_COLUMNS = {"date", "diesel_b7_price", "source"}


def _load_fetch_module():
    """Load data/scripts/fetch_fuel_prices.py as a fresh module."""
    spec = importlib.util.spec_from_file_location(
        "_fetch_fuel_prices_under_test",
        SCRIPTS_DIR / "fetch_fuel_prices.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Seed CSV contract (DATA-02 fallback target)
# ---------------------------------------------------------------------------


class TestSeedCsvContract:
    """The committed seed CSV is the fallback source of truth."""

    def test_seed_csv_exists(self):
        assert SEED_CSV.exists(), f"missing seed CSV at {SEED_CSV}"

    def test_seed_csv_has_required_columns(self):
        df = pd.read_csv(SEED_CSV)
        assert EXPECTED_COLUMNS.issubset(set(df.columns))

    def test_seed_csv_has_at_least_170_rows(self):
        df = pd.read_csv(SEED_CSV)
        assert len(df) >= 170, f"expected >=170 rows, got {len(df)}"

    def test_seed_csv_diesel_prices_realistic(self):
        df = pd.read_csv(SEED_CSV)
        assert df["diesel_b7_price"].between(25.0, 40.0).all()


# ---------------------------------------------------------------------------
# main() fallback behaviour (no live network)
# ---------------------------------------------------------------------------


class TestFallbackBehavior:
    """When ``_scrape_eppo`` blows up, ``main()`` falls back to the seed CSV."""

    def test_main_falls_back_when_scrape_raises_runtime_error(self, capsys):
        module = _load_fetch_module()

        def boom():
            raise RuntimeError("simulated EPPO outage")

        # Replace the scraper with a failing stub so no network call happens.
        module._scrape_eppo = boom  # type: ignore[attr-defined]

        # Should NOT raise -- the fallback path swallows the exception.
        module.main()

        captured = capsys.readouterr().out
        assert "seed CSV fallback" in captured

    def test_main_falls_back_when_requests_get_raises(self, monkeypatch, capsys):
        """End-to-end fallback: real ``_scrape_eppo`` runs, but its first
        ``requests.get`` raises a connection error -- the seed CSV is used.
        """
        module = _load_fetch_module()

        def boom_get(*args, **kwargs):
            import requests

            raise requests.exceptions.ConnectionError("simulated network drop")

        monkeypatch.setattr(module.requests, "get", boom_get)

        module.main()

        captured = capsys.readouterr().out
        assert "seed CSV fallback" in captured

    def test_main_succeeds_on_synthetic_scrape_payload(self, capsys):
        """Sanity check the success branch: a stub returning a valid DF
        should make ``main()`` print the 'Fetched ... from EPPO' status.
        """
        module = _load_fetch_module()

        synthetic = pd.DataFrame(
            {
                "date": ["2026-04-01", "2026-04-02"],
                "diesel_b7_price": [30.5, 30.7],
                "source": ["eppo", "eppo"],
            }
        )
        module._scrape_eppo = lambda: synthetic  # type: ignore[attr-defined]

        # Redirect output away from the committed seed CSV so we don't
        # rewrite the repo's data file during the test.
        # We monkeypatch the module's OUTPUT_PATH after the fact.
        # (Use object.__setattr__ in case OUTPUT_PATH is not a simple attr.)
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_out = Path(tmp) / "out.csv"
            module.OUTPUT_PATH = tmp_out

            module.main()

            captured = capsys.readouterr().out
            assert "Fetched 2 rows from EPPO" in captured
            assert tmp_out.exists()
            written = pd.read_csv(tmp_out)
            assert set(written.columns) == EXPECTED_COLUMNS
            assert len(written) == 2


class TestLoadSeedCsv:
    """Direct unit test for the private fallback helper."""

    def test_load_seed_csv_returns_dataframe(self):
        module = _load_fetch_module()
        df = module._load_seed_csv()
        assert isinstance(df, pd.DataFrame)
        assert EXPECTED_COLUMNS.issubset(set(df.columns))
        assert len(df) >= 170
