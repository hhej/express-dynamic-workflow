"""POST /api/chat — SSE-streamed agent execution (API-01).

Implements the D-17/D-18/D-19 contract:
- First event: type=meta with thread_id (server-generated UUIDv4 when
  client omits it).
- One type=trace event per agent node completion (filtered on
  astream_events on_chain_end + node name in NODE_NAMES).
- One type=answer event when Response Node emits its final_payload.
- On uncaught exception: type=error.
- Stream always closes with type=done.

Phase 5 (Plan 05-02): per-turn config is built by ``_make_config`` so the
Langfuse CallbackHandler attaches with a deterministic trace_id (D-14).
The trace_id pattern is ``seed_trace_id(thread_id, turn_idx)`` and is
exposed via ``config["metadata"]["langfuse_trace_id"]`` so downstream
nodes (e.g. pricing_agent) can read it for the OBS-03 auto-eval Score.
When LANGFUSE_* env vars are missing, ``get_callback_handler`` returns
None and the callbacks list is empty — agent runs identically (D-13).
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.agent.observability import get_callback_handler, seed_trace_id
from backend.api.models import ChatRequest
from backend.api.sse import format_sse

__all__ = ["router"]

logger = logging.getLogger(__name__)
router = APIRouter()

# Filter astream_events output to our node-completion events only.
_NODE_NAMES = {"planner", "fuel_agent", "route_agent", "pricing_agent", "response"}


def _make_config(thread_id: str, turn_idx: int) -> dict:
    """Build the RunnableConfig used by graph.astream_events.

    Centralized so Phase 5 HITL resume (Plan 05-05) reuses the EXACT
    same callbacks + metadata when calling ``Command(resume=...)``. See
    RESEARCH.md Pitfall 1 — divergent fresh vs resume configs orphan
    Langfuse sessions.

    Args:
        thread_id: Conversation thread identifier.
        turn_idx: Zero-indexed turn counter (incremented per user message
            on the same thread). Used by D-14 trace name pattern.

    Returns:
        RunnableConfig dict with:
          - ``configurable.thread_id``: routes the checkpointer.
          - ``callbacks``: ``[CallbackHandler]`` when LANGFUSE_* set, else ``[]``.
          - ``metadata.langfuse_session_id``: thread_id (Langfuse session group).
          - ``metadata.langfuse_user_id``: ``"demo"`` (single-user demo build).
          - ``metadata.langfuse_tags``: ``["express-surcharge", f"turn-{turn_idx}"]``.
          - ``metadata.langfuse_trace_id``: deterministic 32-hex (D-14)
            seeded from ``chat_turn_{thread_id}_{turn_idx}``. Exposed so
            downstream nodes (pricing_agent OBS-03) can attach scores
            without re-deriving the id.
    """
    trace_id = seed_trace_id(thread_id, turn_idx)
    handler = get_callback_handler(trace_id=trace_id)
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": [handler] if handler else [],
        "metadata": {
            "langfuse_session_id": thread_id,
            "langfuse_user_id": "demo",
            "langfuse_tags": ["express-surcharge", f"turn-{turn_idx}"],
            "langfuse_trace_id": trace_id,
        },
    }


async def _next_turn_idx(graph, thread_id: str) -> int:
    """Heuristic: turn_idx = number of prior user messages in this thread.

    Reads from ``graph.aget_state(...)`` which the checkpointer hydrates
    from AsyncSqliteSaver (Phase 3 D-15). For a brand-new thread the
    snapshot.values is empty → returns 0. For an existing thread with N
    prior user messages → returns N (so the about-to-be-sent message is
    turn N indexed).
    """
    try:
        snapshot = await graph.aget_state(
            {"configurable": {"thread_id": thread_id}}
        )
        messages = (snapshot.values or {}).get("messages") or []
        return sum(1 for m in messages if (m or {}).get("role") == "user")
    except Exception:  # noqa: BLE001 — first-ever turn or transient error → 0
        return 0


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """Stream the agent's reasoning + final answer over SSE.

    Phase 5: attaches a Langfuse CallbackHandler with a deterministic
    trace_id (D-14) so the feedback POST (D-16) can score the same
    trace. Falls back to no-op when Langfuse keys are missing (D-13).
    """
    graph = request.app.state.graph
    thread_id = req.thread_id or str(uuid.uuid4())
    # Plan 05-04 will branch here on req.approve != None for HITL resume;
    # Plan 05-02 only wires the fresh-path Langfuse callback.
    if req.message is None:
        # Defensive — fresh path requires a message; HITL resume comes via Plan 05-04.
        raise HTTPException(
            status_code=400,
            detail="message is required for fresh turns",
        )

    turn_idx = await _next_turn_idx(graph, thread_id)
    config = _make_config(thread_id, turn_idx)

    async def stream():
        # D-19: emit meta first so client can persist the thread_id.
        yield format_sse("meta", {"thread_id": thread_id})
        try:
            # Initial state: only the new user message; checkpointer
            # supplies cached fields for follow-ups.
            initial_state = {
                "messages": [{"role": "user", "content": req.message}],
            }
            async for event in graph.astream_events(
                initial_state, config=config, version="v2"
            ):
                ev_type = event.get("event")
                name = event.get("name", "")
                if ev_type == "on_chain_end" and name in _NODE_NAMES:
                    output = (event.get("data") or {}).get("output") or {}
                    # Per Pattern 4 + RESEARCH note: output is the partial
                    # state returned by the node, not the cumulative state.
                    # Stream every reasoning_trace entry the node emitted.
                    for entry in (output.get("reasoning_trace") or []):
                        yield format_sse("trace", entry)
                    # Response Node returns final_payload key (Plan 03-02).
                    if name == "response" and "final_payload" in output:
                        yield format_sse("answer", output["final_payload"])
        except Exception as exc:  # noqa: BLE001 — last-line SSE error
            logger.exception("Chat stream failed")
            yield format_sse(
                "error",
                {"message": str(exc), "retryable": False},
            )
        finally:
            yield format_sse("done", {})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Pitfall 5: prevent proxy buffering
            "Connection": "keep-alive",
        },
    )
