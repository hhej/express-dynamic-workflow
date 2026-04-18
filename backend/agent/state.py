"""Agent state schema for the LangGraph orchestrator (ORCH-06)."""
from __future__ import annotations

import operator
from typing import List, Optional, TypedDict

from typing_extensions import Annotated


class AgentState(TypedDict):
    """Central state for the LangGraph agent graph.

    All agent nodes read from and write to this state dict.
    Fields use snake_case per project conventions.
    """

    messages: List[dict]
    """Conversation history (upgrade to BaseMessage in Phase 3)."""

    fuel_data: Optional[dict]
    """FuelData.model_dump() output, or None."""

    route_data: Optional[dict]
    """RouteData.model_dump() output, or None."""

    shipping_type: Optional[str]
    """One of: bounce, retail_standard, retail_fast."""

    weight_kg: Optional[float]
    """Shipment weight in kg."""

    surcharge_result: Optional[dict]
    """SurchargeResult.model_dump() output, or None."""

    reasoning_trace: Annotated[List[dict], operator.add]
    """Steps taken by agents for transparency.

    Uses operator.add as the LangGraph reducer so multiple nodes (including
    parallel Send nodes in Phase 5) can each append their own trace entry
    without stomping each other's writes. See Phase 2 Pitfall 1.
    """

    next_step: str
    """Routing key for conditional edges."""
