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
        # Bounds widened from 25-40 to 10-60: 999.7 backfill (Bangchak)
        # added P09 monthly aggregates back to 2003 (low: 12.84 in 2003-06)
        # and the April 2026 post-subsidy spike (high: 50.54 on 2026-04-05).
        assert df["diesel_b7_price"].between(10.0, 60.0).all()


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


# ---------------------------------------------------------------------------
# EPPO scraper internals -- new in fix-eppo-scraper-url-restructure
# ---------------------------------------------------------------------------


class TestScrapeEppoInternals:
    """Unit tests for the rewritten ``_scrape_eppo`` (no live network).

    The 2026-05 fix retargets EPPO's renamed petroleum-statistics page and
    parses Table 9 (P09.xls) directly. These tests stub the network calls
    so they exercise the parsing + merge logic against synthetic fixtures.
    """

    def test_oil_share_parser_extracts_diesel_b7_price(self, monkeypatch):
        """``_scrape_oil_share_today`` returns the first numeric price after
        the diesel-B7 image label, ignoring HTML comments."""
        module = _load_fetch_module()

        sample_html = """
        <div class='oil_price_colum_name'>
          <img src='../images/oil-content/oil_name3.png'>
        </div>
        <div class='oil_price_colum'>42.45</div>
        <div class='oil_price_colum_name'>
          <img src='../images/oil-content/oil_name6v2.png'>
        </div>
        <!--<div class='oil_price_colum'>99.99</div>-->
        <div class='oil_price_colum'>39.95</div>
        <div class='oil_price_colum'>40.00</div>
        """

        class _Resp:
            text = sample_html

            def raise_for_status(self):
                return None

        monkeypatch.setattr(module.requests, "get", lambda *a, **k: _Resp())

        price = module._scrape_oil_share_today()
        assert price == 39.95

    def test_oil_share_parser_returns_none_on_missing_label(
        self, monkeypatch
    ):
        """Returns None (not raise) when the diesel-B7 label image isn't
        on the page -- soft failure so ``_scrape_eppo`` can still emit
        P09 monthly rows."""
        module = _load_fetch_module()

        class _Resp:
            text = "<html><body>no diesel label here</body></html>"

            def raise_for_status(self):
                return None

        monkeypatch.setattr(module.requests, "get", lambda *a, **k: _Resp())

        assert module._scrape_oil_share_today() is None

    def test_p09_parser_emits_monthly_rows_with_first_of_month_dates(self):
        """Parsing the live P09.xls should yield one row per month per
        year, dated YYYY-MM-01, with realistic diesel prices."""
        module = _load_fetch_module()
        # Use the committed seed CSV's neighbour file path for stability:
        # the test only runs if a freshly-downloaded P09 sample exists in
        # /tmp (placed there during the manual debug session). Skip
        # otherwise to keep CI offline by default.
        from pathlib import Path as _P

        sample = _P("/tmp/eppo_P09.xls")
        if not sample.exists():
            pytest.skip("/tmp/eppo_P09.xls not present (offline-only test)")

        df = module._parse_p09_workbook(sample.read_bytes())
        assert isinstance(df, pd.DataFrame)
        assert set(df.columns) == EXPECTED_COLUMNS
        # All dates are YYYY-MM-01.
        assert df["date"].str.endswith("-01").all()
        # Decade of monthly data should include modern years.
        years = pd.to_datetime(df["date"]).dt.year
        assert years.max() >= 2025
        # Realistic baht/litre range covering the post-2020 era.
        assert df["diesel_b7_price"].between(10.0, 60.0).all()

    def test_scrape_eppo_merges_p09_with_existing_seed(
        self, tmp_path, monkeypatch
    ):
        """``_scrape_eppo`` keeps daily seed rows AND appends rows after
        the seed max date (P09 monthly + today's snapshot)."""
        module = _load_fetch_module()

        # Pretend the existing CSV ends 2026-04-03 (matches the real seed).
        seed = tmp_path / "seed.csv"
        existing = pd.DataFrame(
            {
                "date": ["2026-03-31", "2026-04-01", "2026-04-03"],
                "diesel_b7_price": [31.49, 31.57, 31.62],
                "source": ["eppo"] * 3,
            }
        )
        existing.to_csv(seed, index=False)
        monkeypatch.setattr(module, "SEED_PATH", seed)

        # Stub the P09 workbook download.
        class _XlsResp:
            content = b""

            def raise_for_status(self):
                return None

        monkeypatch.setattr(module.requests, "get", lambda *a, **k: _XlsResp())

        # Stub _parse_p09_workbook to return three monthly aggregates --
        # one OLDER than seed max (must be filtered out) and two NEWER.
        synthetic_p09 = pd.DataFrame(
            {
                "date": ["2026-03-01", "2026-04-01", "2026-05-01"],
                "diesel_b7_price": [32.12, 44.13, 41.50],
                "source": ["eppo"] * 3,
            }
        )
        monkeypatch.setattr(
            module, "_parse_p09_workbook", lambda content: synthetic_p09
        )

        # Stub today's daily snapshot: returns 39.95 for today.
        monkeypatch.setattr(
            module, "_scrape_oil_share_today", lambda: 39.95
        )
        # Pin Bangkok-today to a date AFTER the seed max + after the P09 max.
        monkeypatch.setattr(
            module, "_today_bangkok", lambda: __import__("datetime").date(
                2026, 5, 9
            )
        )

        result = module._scrape_eppo()

        # Existing daily seed rows preserved verbatim.
        assert "2026-03-31" in result["date"].values
        assert "2026-04-01" in result["date"].values
        assert "2026-04-03" in result["date"].values
        # P09 March 2026 row REJECTED (date <= seed max).
        # P09 May 2026 row APPENDED (date > seed max).
        assert "2026-05-01" in result["date"].values
        # Today's daily snapshot APPENDED.
        assert "2026-05-09" in result["date"].values
        # Monotonic-ascending dates.
        assert (
            pd.to_datetime(result["date"]).is_monotonic_increasing
        )
        # No duplicate dates.
        assert result["date"].is_unique

    def test_bangchak_parser_extracts_diesel_b7_events(self):
        """``_parse_bangchak_table`` extracts (date, diesel_b7) from the
        Historical Retail Oil Prices HTML table, decoding DD/MM/YYYY and
        picking column index 2 (diesel B7)."""
        module = _load_fetch_module()
        sample_html = """
        <html><body><table>
          <tr><th>Date</th><th>Baht/Liter</th></tr>
          <tr>
            <td><img src="../HiDiesel.jpg"></td>
            <td><img src="../Diesel.jpg"></td>
            <td><img src="../Premium.jpg"></td>
            <td><img src="../E85.jpg"></td>
            <td><img src="../E20.jpg"></td>
            <td><img src="../GSH91.jpg"></td>
            <td><img src="../GSH95.jpg"></td>
          </tr>
          <tr>
            <td>08/05/2026</td><td>61.25</td><td>39.95</td><td>55.09</td>
            <td>31.39</td><td>35.45</td><td>42.08</td><td>42.45</td>
          </tr>
          <tr>
            <td>05/04/2026</td><td>71.84</td><td>50.54</td><td>65.68</td>
            <td>40.54</td><td>44.69</td><td>52.61</td><td>52.98</td>
          </tr>
        </table></body></html>
        """
        df = module._parse_bangchak_table(sample_html)
        assert set(df.columns) == EXPECTED_COLUMNS
        assert (df["source"] == "bangchak").all()
        # Date conversion: DD/MM/YYYY -> YYYY-MM-DD
        assert "2026-05-08" in df["date"].values
        assert "2026-04-05" in df["date"].values
        # Column 2 = Diesel B7
        diesel_apr5 = df[df["date"] == "2026-04-05"]["diesel_b7_price"].iloc[0]
        assert diesel_apr5 == 50.54

    def test_bangchak_parser_raises_on_missing_table(self):
        """``_parse_bangchak_table`` raises ValueError when the HTML has
        no <table> -- this is what happens when Bangchak's Radware bot
        gate returns a captcha challenge instead of the real page."""
        module = _load_fetch_module()
        with pytest.raises(ValueError, match="no <table> found"):
            module._parse_bangchak_table(
                "<html><body>Radware Captcha Page</body></html>"
            )

    def test_forward_fill_daily_expands_sparse_events(self):
        """``_forward_fill_daily`` carries each price-change event forward
        until the next event, emitting one row per calendar day."""
        module = _load_fetch_module()
        from datetime import date as _date

        events = pd.DataFrame(
            {
                "date": ["2026-04-05", "2026-04-08", "2026-04-09"],
                "diesel_b7_price": [50.54, 50.54, 48.40],
                "source": ["bangchak"] * 3,
            }
        )
        daily = module._forward_fill_daily(
            events, start=_date(2026, 4, 4), end=_date(2026, 4, 11)
        )
        # 2026-04-04 is BEFORE the earliest event -> dropped (no fill source)
        assert "2026-04-04" not in daily["date"].values
        # 2026-04-05..07 carry 50.54 forward
        assert daily[daily["date"] == "2026-04-06"][
            "diesel_b7_price"
        ].iloc[0] == 50.54
        # 2026-04-09..11 carry 48.40 forward (the latest event)
        assert daily[daily["date"] == "2026-04-11"][
            "diesel_b7_price"
        ].iloc[0] == 48.40

    def test_scrape_eppo_handles_oil_share_failure_gracefully(
        self, tmp_path, monkeypatch
    ):
        """When the daily-snapshot fetch fails, ``_scrape_eppo`` still
        returns the P09-merged frame -- it must NOT raise."""
        module = _load_fetch_module()

        seed = tmp_path / "seed.csv"
        pd.DataFrame(
            {
                "date": ["2026-04-01"],
                "diesel_b7_price": [31.57],
                "source": ["eppo"],
            }
        ).to_csv(seed, index=False)
        monkeypatch.setattr(module, "SEED_PATH", seed)

        class _XlsResp:
            content = b""

            def raise_for_status(self):
                return None

        monkeypatch.setattr(module.requests, "get", lambda *a, **k: _XlsResp())
        monkeypatch.setattr(
            module,
            "_parse_p09_workbook",
            lambda content: pd.DataFrame(
                {
                    "date": ["2026-05-01"],
                    "diesel_b7_price": [41.50],
                    "source": ["eppo"],
                }
            ),
        )

        def boom():
            raise RuntimeError("oil-share unreachable")

        monkeypatch.setattr(module, "_scrape_oil_share_today", boom)

        # Must NOT raise.
        result = module._scrape_eppo()

        # Frame still includes seed row + P09 row.
        assert "2026-04-01" in result["date"].values
        assert "2026-05-01" in result["date"].values
