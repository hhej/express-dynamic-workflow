"""ORCH-09: HITL approval gate (D-04 / D-05 / D-08).

Placed between pricing_agent and response_node (Phase 5 Pitfall 6:
the pricing -> planner edge from Phase 3 is REPLACED with
pricing -> hitl_gate -> response). For low-value totals
(<= HITL_TOTAL_THB_THRESHOLD) the gate is a pass-through that sets
``approval_decision='approve'`` with NO trace entry — zero overhead on
the common case. For high-value totals the gate emits a 'warn' trace
entry AND calls ``langgraph.types.interrupt()``, suspending the run
until the chat handler resumes via ``Command(resume=approve_bool)``.

The ``interrupt()`` return value is the resume value supplied by the
caller. We map ``True`` (or the literal string ``"approve"``) to
``approval_decision='approve'`` and anything else to ``'deny'``, then
emit a second 'ok' trace entry recording the decision (D-08).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.types import interrupt

from backend.config import HITL_TOTAL_THB_THRESHOLD

__all__ = ["hitl_gate_node"]

logger = logging.getLogger(__name__)


def _ts() -> str:
    """ISO-8601 UTC 'Z' timestamp matching Phase 3 D-13."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def hitl_gate_node(state: dict) -> dict:
    """D-05 gate. Pass-through for low-value, interrupt() for high-value.

    Args:
        state: Full AgentState-shaped dict. Reads ``surcharge_result.total``
            to decide whether to pause; reads ``reasoning_trace`` length
            to compute the next ``step`` index for trace entries.

    Returns:
        Partial state dict. Bypass path returns just
        ``{"approval_decision": "approve"}`` (no trace). Interrupt path
        returns ``{"approval_decision": "approve" | "deny",
        "reasoning_trace": [pre_trace, post_trace]}`` after the chat
        handler resumes the graph via ``Command(resume=...)``.
    """
    sr = state.get("surcharge_result") or {}
    total = float(sr.get("total") or 0.0)

    if total <= HITL_TOTAL_THB_THRESHOLD:
        # D-04 low-value pass-through. Zero trace entries, just sets the
        # decision so response_node sees approval_decision='approve'.
        return {"approval_decision": "approve"}

    prior = len(state.get("reasoning_trace") or [])

    pre_trace = {
        "step": prior + 1,
        "agent": "hitl_gate",
        "tool": "interrupt",
        "tool_input": {
            "threshold": HITL_TOTAL_THB_THRESHOLD,
            "total": total,
        },
        "tool_output": {"decision_pending": True},
        "reasoning": (
            f"Total {total:.2f} THB exceeds threshold "
            f"{HITL_TOTAL_THB_THRESHOLD:.2f} THB; awaiting user approval."
        ),
        "timestamp": _ts(),
        "status": "warn",
    }

    # interrupt() returns the resume value when the graph is invoked
    # again with Command(resume=value). Caller passes a bool (or 'approve').
    decision_value = interrupt({
        "type": "approval_required",
        "surcharge_result": sr,
        "threshold": HITL_TOTAL_THB_THRESHOLD,
    })

    approval = "approve" if decision_value in (True, "approve") else "deny"

    post_trace = {
        "step": prior + 2,
        "agent": "hitl_gate",
        "tool": "interrupt",
        "tool_input": {},
        "tool_output": {"decision": approval},
        "reasoning": f"User decision: {approval}",
        "timestamp": _ts(),
        "status": "ok",
    }

    return {
        "approval_decision": approval,
        "reasoning_trace": [pre_trace, post_trace],
    }
