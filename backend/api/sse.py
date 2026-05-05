"""SSE envelope formatter (D-18).

Manual framing because EventSourceResponse is not available in
FastAPI 0.128.8 (Pitfall 5). Each event is one ``data: <json>\\n\\n`` line.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Literal

__all__ = ["format_sse", "EventType"]

EventType = Literal[
    "meta",
    "trace",
    "answer",
    "error",
    "done",
    # Phase 5 D-06 sixth event type — emitted by POST /api/chat when the
    # graph pauses on the HITL gate (interrupt). Carries the surcharge
    # breakdown + threshold so the FE can render Approve/Deny buttons.
    "approval_required",
]


def format_sse(event_type: EventType, payload: Dict[str, Any]) -> bytes:
    """Format a single SSE event as bytes ready for StreamingResponse.

    Args:
        event_type: One of meta, trace, answer, error, done (D-18).
        payload: Arbitrary JSON-serialisable dict.

    Returns:
        UTF-8 encoded bytes of ``data: <json>\\n\\n``.
    """
    body = {"type": event_type, "payload": payload}
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n".encode("utf-8")
