"""Tests for surcharge calculation with hand-calculated values (D-12).

Each test case uses pre-computed expected values to verify the surcharge
formula matches the specification exactly.
"""
from __future__ import annotations

import pytest

from backend.agent.tools.calculate_surcharge import calculate_surcharge
from backend.agent.tools.models import SurchargeResult


class TestSurchargeCalculation:
    """Core surcharge calculation tests with hand-calculated values."""

    def test_case1_bounce_at_baseline_no_traffic(self):
        """Bounce at baseline diesel price with traffic_severity=1.

        fuel_delta_pct = (29.94 - 29.94) / 29.94 = 0.0
        surcharge_pct = 0.0 * 1.0 = 0.0
        traffic adj: 0.0 + 1 * 0.02 = 0.02
        surcharge_amount = 100 * 0.02 = 2.0
        total = 102.0
        """
        result = calculate_surcharge(
            base_rate=100.0,
            current_diesel_price=29.94,
            shipping_type="bounce",
            traffic_severity=1,
        )
        assert isinstance(result, SurchargeResult)
        assert result.surcharge_pct == 0.02
        assert result.surcharge_amount == 2.0
        assert result.total == 102.0
        assert result.capped is False

    def test_case2_retail_standard_above_baseline(self):
        """Retail standard with diesel price above baseline.

        fuel_delta_pct = (32.94 - 29.94) / 29.94 = 0.10020...
        surcharge_pct = 0.10020 * 0.5 = 0.05010...
        NO traffic adj (not bounce)
        surcharge_amount = 200 * 0.0501 = 10.02
        total = 210.02
        """
        result = calculate_surcharge(
            base_rate=200.0,
            current_diesel_price=32.94,
            shipping_type="retail_standard",
            traffic_severity=3,
        )
        assert isinstance(result, SurchargeResult)
        assert result.surcharge_pct == pytest.approx(0.0501, abs=1e-4)
        assert result.surcharge_amount == pytest.approx(10.02, abs=0.01)
        assert result.total == pytest.approx(210.02, abs=0.01)
        assert result.capped is False

    def test_case3_retail_fast_below_baseline_floor_hit(self):
        """Retail fast with diesel below baseline -- floor hit.

        fuel_delta_pct = (28.00 - 29.94) / 29.94 = -0.06479...
        surcharge_pct = -0.06479 * 0.8 = -0.05183...
        Floor hit: clamp to -0.05
        surcharge_amount = 150 * -0.05 = -7.50
        total = 142.50
        """
        result = calculate_surcharge(
            base_rate=150.0,
            current_diesel_price=28.00,
            shipping_type="retail_fast",
            traffic_severity=1,
        )
        assert isinstance(result, SurchargeResult)
        assert result.surcharge_pct == -0.05
        assert result.surcharge_amount == -7.50
        assert result.total == 142.50
        assert result.capped is True

    def test_case4_bounce_high_price_high_traffic_cap_hit(self):
        """Bounce with high price + high traffic -- cap hit.

        fuel_delta_pct = (33.00 - 29.94) / 29.94 = 0.10220...
        surcharge_pct = 0.10220 * 1.0 = 0.10220
        traffic adj: 0.10220 + 5 * 0.02 = 0.20220
        Cap hit: clamp to 0.15
        surcharge_amount = 100 * 0.15 = 15.0
        total = 115.0
        """
        result = calculate_surcharge(
            base_rate=100.0,
            current_diesel_price=33.00,
            shipping_type="bounce",
            traffic_severity=5,
        )
        assert isinstance(result, SurchargeResult)
        assert result.surcharge_pct == 0.15
        assert result.surcharge_amount == 15.0
        assert result.total == 115.0
        assert result.capped is True

    def test_case5_invalid_shipping_type(self):
        """Invalid shipping_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid shipping_type"):
            calculate_surcharge(
                base_rate=100.0,
                current_diesel_price=30.0,
                shipping_type="express",
            )

    def test_case6_negative_base_rate(self):
        """Negative base_rate raises ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_surcharge(
                base_rate=-50.0,
                current_diesel_price=30.0,
                shipping_type="bounce",
            )

    def test_case7a_traffic_severity_zero(self):
        """Traffic severity 0 raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-5"):
            calculate_surcharge(
                base_rate=100.0,
                current_diesel_price=30.0,
                shipping_type="bounce",
                traffic_severity=0,
            )

    def test_case7b_traffic_severity_six(self):
        """Traffic severity 6 raises ValueError."""
        with pytest.raises(ValueError, match="must be 1-5"):
            calculate_surcharge(
                base_rate=100.0,
                current_diesel_price=30.0,
                shipping_type="bounce",
                traffic_severity=6,
            )

    def test_case8_exact_cap_boundary(self):
        """Exact cap boundary -- surcharge_pct exactly at 0.15 is NOT capped.

        We need to find inputs where surcharge_pct == 0.15 before clamping.
        For bounce: surcharge_pct = fuel_delta * 1.0 + traffic * 0.02
        If traffic=5: we need fuel_delta = 0.15 - 0.10 = 0.05
        fuel_delta = 0.05 means current = 29.94 * 1.05 = 31.437
        surcharge_pct = 0.05 + 0.10 = 0.15 exactly -> capped=False
        """
        # Exact 0.15: should NOT be capped
        current_price = 29.94 * 1.05  # = 31.437
        result = calculate_surcharge(
            base_rate=100.0,
            current_diesel_price=current_price,
            shipping_type="bounce",
            traffic_severity=5,
        )
        assert result.surcharge_pct == 0.15
        assert result.capped is False

    def test_case8b_just_above_cap(self):
        """Just above cap -- capped=True.

        If fuel_delta slightly above 0.05 with traffic=5 -> total > 0.15
        """
        result = calculate_surcharge(
            base_rate=100.0,
            current_diesel_price=31.50,  # delta = 1.56/29.94 = 0.0521
            shipping_type="bounce",
            traffic_severity=5,
        )
        # 0.0521 + 0.10 = 0.1521 > 0.15 -> capped
        assert result.surcharge_pct == 0.15
        assert result.capped is True

    def test_case9_retail_standard_no_traffic_adjustment(self):
        """Retail standard with traffic_severity=5 gets NO traffic adjustment.

        fuel_delta_pct = 0.0 (baseline price)
        surcharge_pct = 0.0 * 0.5 = 0.0
        NO traffic adj for non-bounce
        """
        result = calculate_surcharge(
            base_rate=100.0,
            current_diesel_price=29.94,
            shipping_type="retail_standard",
            traffic_severity=5,
        )
        assert result.surcharge_pct == 0.0
        assert result.surcharge_amount == 0.0
        assert result.total == 100.0
        assert result.capped is False

    def test_zero_base_rate_raises(self):
        """Zero base_rate should also raise ValueError."""
        with pytest.raises(ValueError, match="must be positive"):
            calculate_surcharge(
                base_rate=0.0,
                current_diesel_price=30.0,
                shipping_type="bounce",
            )

    def test_returns_surcharge_result_model(self):
        """Function must return a SurchargeResult Pydantic model."""
        result = calculate_surcharge(
            base_rate=100.0,
            current_diesel_price=29.94,
            shipping_type="bounce",
            traffic_severity=1,
        )
        assert isinstance(result, SurchargeResult)
        # Verify all fields exist
        assert hasattr(result, "surcharge_pct")
        assert hasattr(result, "surcharge_amount")
        assert hasattr(result, "total")
        assert hasattr(result, "capped")
