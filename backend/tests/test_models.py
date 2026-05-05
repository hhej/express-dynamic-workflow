"""Tests for Pydantic models, AgentState, and config defaults."""
import pytest
from pydantic import ValidationError

from backend.agent.tools.models import (
    FuelData,
    RateResult,
    RouteData,
    SurchargeInput,
    SurchargeResult,
)
from backend.agent.state import AgentState
from backend import config


class TestSurchargeInput:
    """Validation tests for SurchargeInput model."""

    def test_valid_input(self):
        si = SurchargeInput(
            base_rate=100,
            current_diesel_price=31.0,
            shipping_type="bounce",
        )
        assert si.base_rate == 100
        assert si.traffic_severity == 1  # default

    def test_negative_base_rate_rejected(self):
        with pytest.raises(ValidationError):
            SurchargeInput(
                base_rate=-1,
                current_diesel_price=31.0,
                shipping_type="bounce",
            )

    def test_zero_base_rate_rejected(self):
        with pytest.raises(ValidationError):
            SurchargeInput(
                base_rate=0,
                current_diesel_price=31.0,
                shipping_type="bounce",
            )

    def test_traffic_severity_too_low(self):
        with pytest.raises(ValidationError):
            SurchargeInput(
                base_rate=100,
                current_diesel_price=31.0,
                shipping_type="bounce",
                traffic_severity=0,
            )

    def test_traffic_severity_too_high(self):
        with pytest.raises(ValidationError):
            SurchargeInput(
                base_rate=100,
                current_diesel_price=31.0,
                shipping_type="bounce",
                traffic_severity=6,
            )

    def test_default_traffic_severity(self):
        si = SurchargeInput(
            base_rate=50,
            current_diesel_price=30.0,
            shipping_type="retail_standard",
        )
        assert si.traffic_severity == 1


class TestSurchargeResult:
    """Validation tests for SurchargeResult model."""

    def test_valid_result(self):
        sr = SurchargeResult(
            surcharge_pct=0.05,
            surcharge_amount=5.0,
            total=105.0,
            capped=False,
        )
        assert sr.capped is False
        assert sr.surcharge_pct == 0.05


class TestFuelData:
    """Validation tests for FuelData model."""

    def test_valid_fuel_data(self):
        fd = FuelData(
            price=31.5,
            date="2026-04-01",
            source="eppo",
            baseline=29.94,
            delta_pct=0.052,
        )
        assert fd.unit == "THB/L"  # default

    def test_fuel_data_all_fields(self):
        fd = FuelData(
            price=30.0,
            date="2026-03-15",
            unit="THB/L",
            source="ptt",
            baseline=29.94,
            delta_pct=0.002,
        )
        assert fd.source == "ptt"


class TestRouteData:
    """Validation tests for RouteData model."""

    def test_traffic_severity_bounds_low(self):
        with pytest.raises(ValidationError):
            RouteData(
                origin="BKK",
                destination="NBI",
                distance_km=30.0,
                duration_min=45,
                traffic_severity=0,
                zone="central-1",
            )

    def test_traffic_severity_bounds_high(self):
        with pytest.raises(ValidationError):
            RouteData(
                origin="BKK",
                destination="NBI",
                distance_km=30.0,
                duration_min=45,
                traffic_severity=6,
                zone="central-1",
            )

    def test_valid_route_data(self):
        rd = RouteData(
            origin="Bangkok",
            destination="Nonthaburi",
            distance_km=25.5,
            duration_min=40,
            traffic_severity=3,
            zone="central-1",
        )
        assert rd.zone == "central-1"


class TestRateResult:
    """Validation tests for RateResult model."""

    def test_default_currency(self):
        rr = RateResult(base_rate=100.0, rate_tier="0-5kg")
        assert rr.currency == "THB"

    def test_explicit_currency(self):
        rr = RateResult(base_rate=200.0, currency="USD", rate_tier="5-10kg")
        assert rr.currency == "USD"


class TestAgentState:
    """Validation tests for AgentState TypedDict."""

    def test_state_shape(self):
        state: AgentState = {
            "messages": [],
            "fuel_data": None,
            "route_data": None,
            "shipping_type": None,
            "weight_kg": None,
            "surcharge_result": None,
            "reasoning_trace": [],
            "next_step": "start",
        }
        assert len(state) == 8

    def test_state_with_data(self):
        state: AgentState = {
            "messages": [{"role": "user", "content": "test"}],
            "fuel_data": {"price": 31.0},
            "route_data": {"distance_km": 25.5},
            "shipping_type": "bounce",
            "weight_kg": 3.5,
            "surcharge_result": {"total": 105.0},
            "reasoning_trace": [{"step": "plan"}],
            "next_step": "fetch_fuel",
        }
        assert state["shipping_type"] == "bounce"
        assert state["weight_kg"] == 3.5


class TestConfig:
    """Tests for environment-loaded configuration defaults."""

    def test_baseline_default(self):
        assert config.BASELINE_DIESEL_PRICE == 29.94

    def test_cap_default(self):
        assert config.SURCHARGE_CAP == 0.15

    def test_floor_default(self):
        assert config.SURCHARGE_FLOOR == -0.05

    def test_shipping_multipliers(self):
        assert config.SHIPPING_MULTIPLIERS == {
            "bounce": 1.0,
            "retail_standard": 0.5,
            "retail_fast": 0.8,
        }

    def test_database_path_default(self):
        assert config.DATABASE_PATH == "data/express.db"

    def test_checkpoint_path_default(self):
        assert config.CHECKPOINT_PATH == "data/checkpoints.db"
