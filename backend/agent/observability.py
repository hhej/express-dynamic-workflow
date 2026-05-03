"""Langfuse observability helpers (D-13/D-14/D-15/D-16).

Graceful no-op pattern: when any of LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY,
or LANGFUSE_SECRET_KEY is missing, every helper returns None / silently
swallows the call. This preserves CLAUDE.md local-reproducibility:
the agent runs identically without Langfuse keys.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    """All three keys must be set for Langfuse to engage."""
    return all(
        os.environ.get(k)
        for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")
    )


def get_langfuse_client():
    """Returns initialized Langfuse client, or None when keys missing."""
    if not _enabled():
        return None
    try:
        from langfuse import get_client

        return get_client()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse init failed: %s", exc)
        return None


def get_callback_handler(trace_id: Optional[str] = None):
    """Returns a Langfuse CallbackHandler, or None when keys missing.

    Args:
        trace_id: deterministic trace id (D-14). If provided, the
            handler uses trace_context to ensure the resulting trace
            has this exact id, so D-16 feedback can score it without
            a name lookup.
    """
    if not _enabled():
        return None
    try:
        from langfuse.langchain import CallbackHandler

        if trace_id:
            return CallbackHandler(trace_context={"trace_id": trace_id})
        return CallbackHandler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("CallbackHandler init failed: %s", exc)
        return None


def seed_trace_id(thread_id: str, turn_idx: int) -> str:
    """Deterministic 32-hex trace_id seeded by D-14 name pattern.

    Both the CallbackHandler init (per-turn) and the feedback POST
    handler call this with the same (thread_id, turn_idx) and get the
    same trace_id back, so the feedback Score attaches to the right
    trace WITHOUT a search/lookup.
    """
    client = get_langfuse_client()
    if client is None:
        # No-op fallback for tests / no-key mode: stable hex32 hash.
        import hashlib

        return hashlib.md5(
            f"chat_turn_{thread_id}_{turn_idx}".encode()
        ).hexdigest()
    return client.create_trace_id(seed=f"chat_turn_{thread_id}_{turn_idx}")


def post_formula_accuracy_score(
    trace_id: str,
    base_rate: float,
    current_diesel_price: float,
    shipping_type: str,
    traffic_severity: int,
    agent_result: dict,
) -> None:
    """D-15 fire-and-forget formula accuracy auto-eval.

    Re-runs the Phase 1 pure function (NOT the @tool wrapper — that
    goes through the agent path, defeating eval independence) and
    posts a Score. Any failure is logged and swallowed — eval failure
    MUST NOT impact the user response.
    """
    client = get_langfuse_client()
    if client is None:
        return
    try:
        from backend.agent.tools.calculate_surcharge import calculate_surcharge

        oracle = calculate_surcharge(
            base_rate=base_rate,
            current_diesel_price=current_diesel_price,
            shipping_type=shipping_type,
            traffic_severity=traffic_severity,
        )
        agent_total = float(agent_result.get("total") or 0.0)
        match = abs(oracle.total - agent_total) < 1e-6
        client.create_score(
            trace_id=trace_id,
            name="formula_accuracy",
            value=1.0 if match else 0.0,
            data_type="NUMERIC",
            comment=None if match else f"oracle={oracle.total} agent={agent_total}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("formula_accuracy auto-eval failed (non-fatal): %s", exc)
