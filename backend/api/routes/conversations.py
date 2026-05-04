"""GET /api/conversations + GET /api/conversations/:id (API-02, API-03).

Lists past conversation threads via the AsyncSqliteSaver checkpoints
table, and returns the latest state snapshot for a single thread via
``compiled_graph.aget_state()`` (Pitfall 6: ``aget_state`` returns a
flat ``StateSnapshot.values`` dict, avoiding ``CheckpointTuple``
unpacking).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query, Request

from backend.api.models import ConversationSummary

__all__ = ["router"]

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/conversations", response_model=List[ConversationSummary])
async def list_conversations(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
):
    """List conversation threads ordered by latest activity (newest first).

    Pattern 5 (RESEARCH): query the ``checkpoints`` table directly for
    thread enumeration -- ``AsyncSqliteSaver`` does not expose a
    ``alist_threads()`` helper, so we hit the raw SQL via the open
    aiosqlite connection that the lifespan stashed on
    ``app.state.checkpointer.conn``.

    For each thread we then call ``graph.aget_state()`` to fetch the
    latest ``StateSnapshot.values`` dict and pull a 100-char preview of
    the first user message. ``aget_state`` failures are non-fatal -- a
    blank preview is preferable to a 500 because the listing call
    should remain robust to corrupted/partial checkpoints.
    """
    checkpointer = request.app.state.checkpointer
    graph = request.app.state.graph

    async with checkpointer.conn.execute(
        """
        SELECT thread_id, MAX(checkpoint_id) AS latest
        FROM checkpoints
        GROUP BY thread_id
        ORDER BY latest DESC
        LIMIT ?
        """,
        (limit,),
    ) as cur:
        rows = await cur.fetchall()

    summaries: list[ConversationSummary] = []
    for thread_id, latest in rows:
        cfg = {"configurable": {"thread_id": thread_id}}
        preview = ""
        try:
            snap = await graph.aget_state(cfg)
            msgs = (snap.values or {}).get("messages") or []
            if msgs:
                first = msgs[0]
                if isinstance(first, dict):
                    content = first.get("content") or ""
                else:
                    # langchain_core BaseMessage instances expose .content
                    content = getattr(first, "content", "") or str(first)
                preview = (content or "")[:100]
        except Exception:  # noqa: BLE001 -- preview is best-effort
            logger.warning(
                "aget_state failed for thread_id=%s; preview omitted",
                thread_id,
            )

        summaries.append(
            ConversationSummary(
                thread_id=thread_id,
                last_updated=str(latest),
                first_message_preview=preview,
            )
        )
    return summaries


def _attach_message_ids(
    messages: list[Dict[str, Any]],
    thread_id: str,
) -> list[Dict[str, Any]]:
    """Attach message_id to the LAST assistant message of each turn.

    Turn rule (Phase 7 D-07, mirrors backend/api/routes/chat.py:_next_turn_idx):
    one user message starts one turn; assistants belong to the most recent
    preceding user message's turn. ONLY the LAST assistant per turn is
    canonical (the one a thumbs vote should score). User messages and
    non-last in-turn assistant rows get NO message_id field — silent
    absence is the FE gate signal (D-06, D-08).

    Args:
        messages: Raw messages list from the AgentState snapshot.
        thread_id: Conversation thread identifier (Phase 7 D-02 single
            source of truth for the FULL message_id string).

    Returns:
        Copy of messages with message_id stamped on canonical assistants.
    """
    # First pass: which turn (zero-indexed) does each row belong to?
    turn_for: list[int] = []
    n_users_seen = 0
    for m in messages:
        if (m or {}).get("role") == "user":
            n_users_seen += 1
        turn_for.append(max(0, n_users_seen - 1))

    # Second pass: which row is the LAST assistant in each turn?
    last_assistant_per_turn: dict[int, int] = {}
    for i, m in enumerate(messages):
        if (m or {}).get("role") == "assistant":
            last_assistant_per_turn[turn_for[i]] = i
    last_indices = set(last_assistant_per_turn.values())

    # Third pass: emit copies, stamping message_id on canonical assistants only.
    out: list[Dict[str, Any]] = []
    for i, m in enumerate(messages):
        m_out = dict(m or {})
        if i in last_indices:
            m_out["message_id"] = f"{thread_id}-{turn_for[i]}"
        out.append(m_out)
    return out


@router.get("/api/conversations/{thread_id}")
async def get_conversation(
    thread_id: str, request: Request
) -> Dict[str, Any]:
    """Return the latest ``AgentState`` snapshot for a single thread.

    Uses ``graph.aget_state()`` (Pitfall 6) so we get the merged-state
    ``StateSnapshot.values`` dict directly -- avoids manually unpacking
    a ``CheckpointTuple.checkpoint["channel_values"]`` payload.

    Returns HTTP 404 when the thread has no checkpoints (or the snapshot
    has no messages, which is the same outcome from a client's
    perspective).
    """
    graph = request.app.state.graph
    cfg = {"configurable": {"thread_id": thread_id}}
    snap = await graph.aget_state(cfg)
    values = snap.values if snap is not None else None
    if not values or not values.get("messages"):
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {thread_id} not found",
        )
    return {
        "thread_id": thread_id,
        "messages": _attach_message_ids(
            values.get("messages") or [],
            thread_id,
        ),
        "surcharge_result": values.get("surcharge_result"),
        "reasoning_trace": values.get("reasoning_trace") or [],
        "fuel_data": values.get("fuel_data"),
        "route_data": values.get("route_data"),
        "errors": values.get("errors") or [],
    }
