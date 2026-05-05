"""TOOL-04: LangGraph @tool wrapper around the Phase 1 pure surcharge function.

Phase 1's calculate_surcharge() is a pure, fully tested function. This
wrapper adds LangChain's @tool surface so the Pricing Agent (Phase 3)
can invoke it via `tool.invoke({...})` or via Gemini function-calling.
"""
from __future__ import annotations

from langchain_core.tools import tool

from backend.agent.tools.calculate_surcharge import (
    calculate_surcharge as _calc,
)
from backend.agent.tools.models import SurchargeInput, SurchargeResult

__all__ = ["calculate_surcharge_tool"]


@tool("calculate_surcharge", args_schema=SurchargeInput)
def calculate_surcharge_tool(
    base_rate: float,
    current_diesel_price: float,
    shipping_type: str,
    traffic_severity: int = 1,
) -> SurchargeResult:
    """Calculate fuel surcharge for a shipment.

    Thin wrapper over the Phase 1 pure function. Pydantic input validation
    is handled by the SurchargeInput args_schema; ValueError from the inner
    function surfaces to the caller unchanged.

    Args:
        base_rate: Base shipping rate in THB (must be > 0).
        current_diesel_price: Current diesel B7 price in THB/L (must be > 0).
        shipping_type: bounce | retail_standard | retail_fast.
        traffic_severity: Traffic severity 1-5 (only affects bounce).

    Returns:
        SurchargeResult(surcharge_pct, surcharge_amount, total, capped).

    Raises:
        ValueError: Propagated from the pure function for invalid inputs.
    """
    return _calc(base_rate, current_diesel_price, shipping_type, traffic_severity)
