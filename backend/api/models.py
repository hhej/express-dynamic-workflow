"""Pydantic request/response models for the FastAPI layer."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

__all__ = [
    "ChatRequest",
    "SSEEvent",
    "ConversationSummary",
    "FuelPricePoint",
    # Phase 5 additions
    "FeedbackRequest",
    "ApprovalRequest",
]


class ChatRequest(BaseModel):
    """POST /api/chat body (API-01).

    Phase 5: optional ``approve`` field carries the HITL resume decision
    when paired with an existing ``thread_id`` (D-06).
    """

    message: Optional[str] = Field(
        default=None,
        min_length=1,
        description=(
            "User message. Required for fresh turns. May be omitted on "
            "a resume call where only `approve` is supplied."
        ),
    )
    thread_id: Optional[str] = Field(
        default=None,
        description=(
            "Conversation thread identifier. If omitted on a fresh turn, "
            "server generates a UUIDv4 and returns it in the first "
            "SSE meta event."
        ),
    )
    approve: Optional[bool] = Field(
        default=None,
        description=(
            "D-06 HITL resume decision. When non-None and `thread_id` is "
            "provided, the chat handler resumes the paused graph with "
            "Command(resume=approve)."
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


# ----- Phase 5 additions -----


class FeedbackRequest(BaseModel):
    """POST /api/feedback body (API-05, D-16).

    Shape mirrors Phase 4 FeedbackButtons localStorage payload verbatim.
    """

    thread_id: str = Field(min_length=1)
    message_id: str = Field(
        min_length=1,
        description=(
            "Phase 5 contract: f'{thread_id}-{turn_idx}'. Backend "
            "extracts turn_idx for seed_trace_id."
        ),
    )
    score: Literal["up", "down"]
    reason: Optional[str] = Field(default=None, max_length=500)


class ApprovalRequest(BaseModel):
    """POST /api/chat resume body when ``approve`` is set.

    Note: ``ChatRequest`` already carries ``thread_id`` and ``approve`` directly;
    ``ApprovalRequest`` is a dedicated alias used by docs/architecture.md for
    clarity, but the chat endpoint accepts either shape.
    """

    thread_id: str = Field(min_length=1)
    approve: bool
