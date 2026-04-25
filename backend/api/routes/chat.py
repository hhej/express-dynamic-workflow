"""POST /api/chat — SSE-streamed agent execution (API-01).

Implements the D-17/D-18/D-19 contract:
- First event: type=meta with thread_id (server-generated UUIDv4 when
  client omits it).
- One type=trace event per agent node completion (filtered on
  astream_events on_chain_end + node name in NODE_NAMES).
- One type=answer event when Response Node emits its final_payload.
- On uncaught exception: type=error.
- Stream always closes with type=done.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.api.models import ChatRequest
from backend.api.sse import format_sse

__all__ = ["router"]

logger = logging.getLogger(__name__)
router = APIRouter()

# Filter astream_events output to our node-completion events only.
_NODE_NAMES = {"planner", "fuel_agent", "route_agent", "pricing_agent", "response"}


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """Stream the agent's reasoning + final answer over SSE."""
    graph = request.app.state.graph
    thread_id = req.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

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
