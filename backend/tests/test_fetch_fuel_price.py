"""Tests for TOOL-01: fetch_fuel_price with 3-level fallback chain."""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from backend.agent.tools import fetch_fuel_price as mod
from backend.agent.tools.fetch_fuel_price import fetch_fuel_price
from backend.agent.tools.models import FuelData
from backend.config import BASELINE_DIESEL_PRICE


def test_falls_back_to_cached_csv_when_live_fails(httpx_mock, monkeypatch):
    """Level 1 fails 3x -> Level 2 CSV serves data."""
    # Skip sleeping to keep test fast.
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))

    result = fetch_fuel_price()

    assert isinstance(result, FuelData)
    assert result.source == "eppo_cached_csv"
    assert result.price > 0
    assert result.unit == "THB/L"
    assert result.baseline == pytest.approx(BASELINE_DIESEL_PRICE)


def test_falls_back_to_baseline_when_csv_missing(httpx_mock, monkeypatch, tmp_path):
    """Level 1 fails, Level 2 CSV absent -> Level 3 baseline."""
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    monkeypatch.setattr(mod, "_FUEL_CSV", tmp_path / "nope.csv")
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))

    result = fetch_fuel_price()

    assert result.source == "hardcoded_baseline"
    assert result.price == pytest.approx(BASELINE_DIESEL_PRICE)
    assert result.delta_pct == pytest.approx(0.0)


def test_falls_back_to_baseline_when_csv_empty(httpx_mock, monkeypatch, tmp_path):
    """Level 1 fails, Level 2 CSV empty -> Level 3 baseline."""
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("date,diesel_b7_price\n")  # header only
    monkeypatch.setattr(mod, "_FUEL_CSV", empty_csv)
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))

    result = fetch_fuel_price()

    assert result.source == "hardcoded_baseline"


def test_retry_backoff_sleeps_1s_then_2s(httpx_mock, monkeypatch):
    """D-04: exponential backoff 1s, 2s between live-scrape retries."""
    sleeps: list = []
    monkeypatch.setattr(mod.time, "sleep", lambda s: sleeps.append(s))
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))

    fetch_fuel_price()

    # First attempt has no sleep; attempts 2 and 3 sleep 1 and 2.
    assert sleeps == [1, 2], f"expected [1, 2], got {sleeps}"


def test_fuel_data_delta_pct_computed_correctly(httpx_mock, monkeypatch):
    """delta_pct reflects (price - baseline) / baseline."""
    monkeypatch.setattr(mod.time, "sleep", lambda _s: None)
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))

    result = fetch_fuel_price()
    expected = round((result.price - BASELINE_DIESEL_PRICE) / BASELINE_DIESEL_PRICE, 4)
    assert result.delta_pct == pytest.approx(expected)


def test_scrape_stub_raises_not_implemented_directly():
    """Open Question 2: live scrape is intentionally stubbed until selectors captured."""
    with pytest.raises(NotImplementedError):
        mod._scrape_eppo_live()
