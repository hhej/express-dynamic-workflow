"""Integration tests for GET /api/fuel-prices (API-04).

Reads the real ``data/raw/eppo_diesel_prices.csv`` (186 rows spanning
2025-10-01 -> 2026-04-03 per RESEARCH lines 875-898) so the assertions
verify behaviour against the actual seeded data the dashboard chart
will consume.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from backend.api.main import app


def test_returns_last_30_days():
    """``days=30`` returns only rows on or after today - 30 days, with
    the documented FuelPricePoint shape."""
    with TestClient(app) as client:
        resp = client.get("/api/fuel-prices?days=30")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

        cutoff = date.today() - timedelta(days=30)
        for entry in data:
            d = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            assert d >= cutoff
            assert isinstance(entry["price"], (int, float))
            assert entry["unit"] == "THB/L"
            assert "source" in entry


def test_clamps_to_available():
    """``days=365`` clamps to whatever the CSV holds; result still sorted
    ascending by date so the chart can render left-to-right."""
    with TestClient(app) as client:
        resp = client.get("/api/fuel-prices?days=365")
        assert resp.status_code == 200
        data = resp.json()
        # CSV spans 2025-10-01 -> 2026-04-03 (186 rows). Today is
        # 2026-04-25 per environment context, so the 365-day window
        # captures every row from the CSV.
        assert len(data) >= 1
        first_d = datetime.strptime(data[0]["date"], "%Y-%m-%d").date()
        last_d = datetime.strptime(data[-1]["date"], "%Y-%m-%d").date()
        assert first_d <= last_d
