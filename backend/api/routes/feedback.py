"""API-05 + OBS-02 — POST /api/feedback handler.

D-16 contract:
- Body shape matches Phase 4 D-17 localStorage payload verbatim.
- Resolves trace_id deterministically from message_id ("{thread_id}-{turn_idx}").
- Calls langfuse.create_score(name="user_feedback", value=1|-1).
- Synchronous (low traffic, simple error surface, no queue).
- Graceful no-op when Langfuse keys missing — returns 200 delivered=false.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException

from backend.agent.observability import get_langfuse_client, seed_trace_id
from backend.api.models import FeedbackRequest

__all__ = ["router"]

logger = logging.getLogger(__name__)
router = APIRouter()

# message_id contract: "{thread_id}-{turn_idx}". The trailing -<digits> suffix
# is the turn index; thread_ids may themselves contain dashes (UUIDv4), so we
# anchor on the LAST -<digits> match.
_TURN_RE = re.compile(r"^(.+)-(\d+)$")


def _parse_message_id(message_id: str) -> tuple[str, int]:
    """Extract (thread_id, turn_idx) from "{thread_id}-{turn_idx}".

    Raises ValueError if shape doesn't match (caller maps to HTTP 400).
    """
    m = _TURN_RE.match(message_id)
    if not m:
        raise ValueError(
            f"message_id must be '{{thread_id}}-{{turn_idx}}'; got {message_id!r}"
        )
    return m.group(1), int(m.group(2))


@router.post("/api/feedback")
async def feedback(req: FeedbackRequest):
    """Forward user feedback to Langfuse as a Score."""
    # Validate message_id shape early.
    try:
        extracted_thread_id, turn_idx = _parse_message_id(req.message_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Sanity check: thread_id in body and parsed thread_id must agree
    # (defense-in-depth — frontend should always send consistent values).
    if extracted_thread_id != req.thread_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"thread_id mismatch: body thread_id={req.thread_id!r} "
                f"but message_id encodes {extracted_thread_id!r}"
            ),
        )

    client = get_langfuse_client()
    if client is None:
        # D-13 graceful no-op — return 200 anyway so frontend doesn't
        # treat missing Langfuse as a user-facing error.
        logger.info("feedback: langfuse disabled, skipping score")
        return {
            "status": "ok",
            "delivered": False,
            "reason": "langfuse_disabled",
        }

    trace_id = seed_trace_id(req.thread_id, turn_idx)
    score_value = 1 if req.score == "up" else -1
    try:
        client.create_score(
            trace_id=trace_id,
            name="user_feedback",
            value=score_value,
            data_type="NUMERIC",
            comment=req.reason,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("feedback: langfuse create_score failed")
        raise HTTPException(status_code=502, detail=str(exc))

    return {
        "status": "ok",
        "delivered": True,
        "trace_id": trace_id,
    }
