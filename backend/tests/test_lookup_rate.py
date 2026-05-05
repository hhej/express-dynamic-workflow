"""Tests for TOOL-03: lookup_rate with half-open weight-tier intervals."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.agent.tools import lookup_rate as mod
from backend.agent.tools.lookup_rate import lookup_rate
from backend.agent.tools.models import RateResult


@pytest.fixture(autouse=True)
def _point_at_seeded_db(monkeypatch, seeded_sqlite_path: Path):
    """Redirect lookup_rate's DB path to the per-test seeded copy."""
    monkeypatch.setattr(mod, "_DB_PATH", seeded_sqlite_path)


def test_known_tier_returns_rate_result():
    result = lookup_rate("bounce", "central-1", 7.5)
    assert isinstance(result, RateResult)
    assert result.base_rate > 0
    assert result.currency == "THB"
    assert "5-10" in result.rate_tier


def test_half_open_boundary_5kg():
    """D-13: 5.0 kg must fall in the 5-10 tier, not 0-5."""
    result = lookup_rate("bounce", "central-1", 5.0)
    assert "5-10" in result.rate_tier


def test_upper_boundary_just_below():
    """4.99 kg falls in 0-5."""
    result = lookup_rate("bounce", "central-1", 4.99)
    assert "0-5" in result.rate_tier


def test_unknown_shipping_type_raises():
    with pytest.raises(ValueError, match="express_fast"):
        lookup_rate("express_fast", "central-1", 10.0)


def test_unknown_zone_raises():
    with pytest.raises(ValueError, match="central-99"):
        lookup_rate("bounce", "central-99", 10.0)


def test_weight_at_or_above_top_tier_raises():
    """Sentinel is 999; half-open excludes equality."""
    with pytest.raises(ValueError):
        lookup_rate("bounce", "central-1", 999.0)


def test_zero_and_negative_weight_raises():
    with pytest.raises(ValueError, match="positive"):
        lookup_rate("bounce", "central-1", 0.0)
    with pytest.raises(ValueError, match="positive"):
        lookup_rate("bounce", "central-1", -1.0)


def test_rate_tier_string_format_top_tier():
    result = lookup_rate("bounce", "central-1", 75.0)
    assert result.rate_tier.endswith("+kg")
    assert result.rate_tier.startswith("50")
