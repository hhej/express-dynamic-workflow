"""Pydantic request/response models for the FastAPI layer."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

__all__ = [
    "ChatRequest",
    "SSEEvent",
    "ConversationSummary",
    "FuelPricePoint",
]


class ChatRequest(BaseModel):
    """POST /api/chat body (API-01)."""

    message: str = Field(min_length=1, description="User message")
    thread_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation thread identifier. If omitted, server "
            "generates a UUIDv4 and returns it in the first SSE meta event."
        ),
    )


class SSEEvent(BaseModel):
    """D-18 SSE envelope shape (informational; not used as response_model)."""

    type: Literal["meta", "trace", "answer", "error", "done"]
    payload: Dict[str, Any] = Field(default_factory=dict)


class ConversationSummary(BaseModel):
    """GET /api/conversations item shape (API-02; populated by Plan 03-05)."""

    thread_id: str
    last_updated: str
    first_message_preview: str = ""


class FuelPricePoint(BaseModel):
    """GET /api/fuel-prices item shape (API-04; populated by Plan 03-05)."""

    date: str
    price: float
    unit: str = "THB/L"
    source: str
