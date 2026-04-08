"""TDD RED: Verify models, state, and config are importable."""
from backend.agent.tools.models import (
    SurchargeInput, SurchargeResult, FuelData, RouteData, RateResult
)
from backend.agent.state import AgentState
from backend import config


def test_surcharge_input_valid():
    si = SurchargeInput(
        base_rate=100, current_diesel_price=31.0, shipping_type="bounce"
    )
    assert si.base_rate == 100
    assert si.traffic_severity == 1


def test_config_defaults():
    assert config.BASELINE_DIESEL_PRICE == 29.94
    assert config.SURCHARGE_CAP == 0.15
    assert config.SURCHARGE_FLOOR == -0.05
