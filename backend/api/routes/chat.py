"""POST /api/chat — SSE-streamed agent execution (API-01).

Implements the D-17/D-18/D-19 contract:
- First event: type=meta with thread_id (server-generated UUIDv4 when
  client omits it).
- One type=trace event per agent node completion (filtered on
  astream_events on_chain_end + node name in NODE_NAMES).
- One type=answer event when Response Node emits its final_payload.
- On uncaught exception: type=error.
- Stream always closes with type=done — EXCEPT when an
  ``approval_required`` event was emitted (Plan 05-05 / D-06 / Pitfall 2),
  in which case the stream closes WITHOUT a trailing done so the FE
  keeps the Approve/Deny buttons live until a resume call is made.

Phase 5 (Plan 05-02): per-turn config is built by ``_make_config`` so the
Langfuse CallbackHandler attaches with a deterministic trace_id (D-14).
The trace_id pattern is ``seed_trace_id(thread_id, turn_idx)`` and is
exposed via ``config["metadata"]["langfuse_trace_id"]`` so downstream
nodes (e.g. pricing_agent) can read it for the OBS-03 auto-eval Score.
When LANGFUSE_* env vars are missing, ``get_callback_handler`` returns
None and the callbacks list is empty — agent runs identically (D-13).

Phase 5 (Plan 05-05) / ORCH-09: when ``ChatRequest.approve`` is non-None,
the handler resumes the paused graph via ``Command(resume=approve)``
reusing the SAME ``_make_config`` helper so Langfuse session continuity
is preserved across the pause (Pitfall 1). The fresh path checks for an
interrupt at the end of the stream and emits a sixth ``approval_required``
SSE event when paused.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from backend.agent.observability import get_callback_handler, seed_trace_id
from backend.api.models import ChatRequest
from backend.api.sse import format_sse

__all__ = ["router"]

logger = logging.getLogger(__name__)
router = APIRouter()

# Filter astream_events output to our node-completion events only.
# Plan 05-04 added ``search_agent``; Plan 05-05 added ``hitl_gate`` (which
# emits its own pre/post-interrupt trace entries via the standard reducer
# — they flow through the same astream_events on_chain_end channel).
_NODE_NAMES = {
    "planner",
    "fuel_agent",
    "route_agent",
    "pricing_agent",
    "search_agent",  # Plan 05-04
    "hitl_gate",     # Plan 05-05
    "response",
}


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
          - ``metadata.langfuse_trace_name``: ``"express-surcharge-agent"`` —
            constant agent name so all traces filter under one Langfuse name.
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
            "langfuse_trace_name": "express-surcharge-agent",
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


async def _drain_events(graph, payload, config, _node_names=_NODE_NAMES):
    """Async generator yielding (event_type, payload_dict) tuples.

    Centralized so fresh and resume paths share the SAME filter logic on
    ``astream_events``. The streaming client receives:
      - ``("trace", entry)`` per node-emitted reasoning_trace entry, in order.
      - ``("answer", final_payload)`` when the response_node emits one.

    Pattern 4 / Plan 03-04 reminder: ``output`` here is the partial state
    dict the node returned, not the cumulative state, so we read
    ``reasoning_trace`` directly off the partial state.
    """
    async for event in graph.astream_events(payload, config=config, version="v2"):
        ev_type = event.get("event")
        name = event.get("name", "")
        if ev_type == "on_chain_end" and name in _node_names:
            output = (event.get("data") or {}).get("output") or {}
            for entry in (output.get("reasoning_trace") or []):
                yield "trace", entry
            if name == "response" and "final_payload" in output:
                yield "answer", output["final_payload"]


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """Stream the agent's reasoning + final answer over SSE.

    Phase 5 (Plan 05-05) / D-06: when ``req.approve`` is non-None, the
    handler treats this as a resume call and invokes the paused graph
    via ``Command(resume=req.approve)``. ``thread_id`` is required in
    that case so the checkpointer can locate the paused state.

    Phase 5 (Plan 05-02): attaches a Langfuse CallbackHandler with a
    deterministic trace_id (D-14) so the feedback POST (D-16) can score
    the same trace. Falls back to no-op when Langfuse keys are missing
    (D-13).
    """
    graph = request.app.state.graph
    thread_id = req.thread_id or str(uuid.uuid4())

    # D-06 resume path: req.approve != None means resume the paused graph.
    if req.approve is not None:
        if not req.thread_id:
            raise HTTPException(
                status_code=400,
                detail="thread_id is required for resume (approve) calls",
            )
        return await _resume_stream(graph, thread_id, req.approve)

    # Fresh-turn path requires a message.
    if req.message is None:
        raise HTTPException(
            status_code=400,
            detail="message is required for fresh turns",
        )

    return await _fresh_stream(graph, thread_id, req.message)


async def _fresh_stream(graph, thread_id: str, message: str):
    """Fresh-turn SSE stream with HITL interrupt detection (Pitfall 2).

    After the underlying ``astream_events`` generator exhausts, we call
    ``aget_state`` to inspect ``snapshot.next``. A non-empty tuple means
    the run paused on a node (the hitl_gate via interrupt()). In that
    case we emit a sixth ``approval_required`` event and CLOSE the
    stream WITHOUT a trailing ``done`` so the FE keeps the Approve/Deny
    buttons live until the resume POST arrives.
    """
    turn_idx = await _next_turn_idx(graph, thread_id)
    config = _make_config(thread_id, turn_idx)

    async def stream():
        # D-19: emit meta first so client can persist the thread_id.
        yield format_sse("meta", {"thread_id": thread_id})
        pending_approval = False
        try:
            initial_state = {
                "messages": [{"role": "user", "content": message}],
            }
            async for kind, payload in _drain_events(
                graph, initial_state, config
            ):
                yield format_sse(kind, payload)

            # After the stream exhausts: check for an interrupt. If the
            # graph paused on the hitl_gate, snapshot.next is non-empty
            # and snapshot.tasks[0].interrupts carries the interrupt
            # payload (D-05 shape: type/surcharge_result/threshold).
            snapshot = await graph.aget_state(config)
            if getattr(snapshot, "next", None):
                pending_approval = True
                interrupts = []
                tasks = getattr(snapshot, "tasks", None) or []
                if tasks:
                    interrupts = getattr(tasks[0], "interrupts", []) or []
                iv = interrupts[0].value if interrupts else {}
                yield format_sse(
                    "approval_required",
                    {
                        "thread_id": thread_id,
                        "surcharge_result": iv.get("surcharge_result"),
                        "threshold": iv.get("threshold"),
                    },
                )
                # Pitfall 2: NO done after approval_required.
                return
        except Exception as exc:  # noqa: BLE001 — last-line SSE error
            logger.exception("Chat stream failed")
            yield format_sse(
                "error",
                {"message": str(exc), "retryable": False},
            )
        finally:
            if not pending_approval:
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


async def _resume_stream(graph, thread_id: str, approve: bool):
    """D-06 resume path — ``Command(resume=approve)``.

    Pitfall 1: REUSES ``_make_config`` so Langfuse callbacks + metadata
    are preserved across the pause. ``_next_turn_idx`` returns the count
    of user messages already on the thread; the resume call does NOT add
    a new user message, so the in-flight turn index is one less than the
    "next fresh turn" that the heuristic would return. We clamp at 0.
    """
    turn_idx = await _next_turn_idx(graph, thread_id)
    cfg_turn = max(0, turn_idx - 1) if turn_idx > 0 else 0
    config = _make_config(thread_id, cfg_turn)

    async def stream():
        yield format_sse("meta", {"thread_id": thread_id})
        try:
            async for kind, payload in _drain_events(
                graph, Command(resume=approve), config
            ):
                yield format_sse(kind, payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chat resume stream failed")
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
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
