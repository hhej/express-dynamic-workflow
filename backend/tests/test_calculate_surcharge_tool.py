"""Tests for TOOL-04: calculate_surcharge_tool LangGraph @tool wrapper."""
from __future__ import annotations

import pytest

from backend.agent.tools.calculate_surcharge import calculate_surcharge
from backend.agent.tools.calculate_surcharge_tool import (
    calculate_surcharge_tool,
)
from backend.agent.tools.models import SurchargeInput, SurchargeResult


def test_tool_has_correct_name_and_args_schema():
    """@tool decorator exposes name + args_schema per LangChain contract."""
    assert calculate_surcharge_tool.name == "calculate_surcharge"
    assert calculate_surcharge_tool.args_schema is SurchargeInput


def test_wrapper_parity_with_pure_function():
    """Tool .invoke must return identical SurchargeResult to the pure function."""
    inputs = dict(
        base_rate=100.0,
        current_diesel_price=32.0,
        shipping_type="retail_standard",
        traffic_severity=1,
    )
    pure = calculate_surcharge(**inputs)
    via_tool = calculate_surcharge_tool.invoke(inputs)
    # @tool invoke can return the Pydantic model directly OR its model_dump;
    # accept either — what matters is structural equality.
    if isinstance(via_tool, SurchargeResult):
        assert via_tool == pure
    else:
        assert via_tool == pure.model_dump()


def test_invoke_with_bounce_and_traffic():
    inputs = dict(
        base_rate=200.0,
        current_diesel_price=35.0,
        shipping_type="bounce",
        traffic_severity=3,
    )
    pure = calculate_surcharge(**inputs)
    via_tool = calculate_surcharge_tool.invoke(inputs)
    if isinstance(via_tool, SurchargeResult):
        assert via_tool == pure
    else:
        assert via_tool == pure.model_dump()


def test_invoke_raises_on_invalid_shipping_type():
    """Invalid shipping_type from the pure function surfaces as ValueError."""
    with pytest.raises(ValueError, match="Invalid shipping_type"):
        calculate_surcharge_tool.invoke(
            dict(
                base_rate=100.0,
                current_diesel_price=30.0,
                shipping_type="express_fast",
                traffic_severity=1,
            )
        )
