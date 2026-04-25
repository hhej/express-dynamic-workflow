"""ORCH-05: Response Node.

Renders the final user-facing payload (D-10) under the ``final_payload`` key
so the chat SSE handler (Plan 03-04) can detect it via ``astream_events``
(see RESEARCH Pattern 4).

D-11 markdown contract:
    - Prose paragraph
    - 4-row markdown table with EXACT row labels:
        | Base rate | <amount> THB |
        | Surcharge % | <pct>% |
        | Surcharge amount | <amount> THB |
        | Total | <amount> THB |
    - Italic footer "*Reasoning trace available below.*"

When ``surcharge_result.capped`` is True, the cap callout
``"> ⚠ Cap/floor applied — review recommended"`` is prepended.

Status precedence (D-10):
    1. state.errors non-empty             -> "partial"
    2. state.clarification_reason set
       AND no surcharge_result            -> "clarify"
    3. surcharge_result present           -> "ok"
    4. fallback                           -> "clarify"

Implementation note: per Plan 03-02 / RESEARCH Open Questions 3 & 5, the
prose summary is rendered with a deterministic Python f-string — no Gemini
call in v1. This keeps response rendering fully deterministic for tests
and avoids burning quota on the final hop.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

__all__ = ["response_node"]

logger = logging.getLogger(__name__)

_FOOTER = "*Reasoning trace available below.*"
_CAP_CALLOUT = "> ⚠ Cap/floor applied — review recommended"


def _render_table(surcharge_result: dict) -> str:
    """Render the 4-row D-11 markdown table from a surcharge_result dict.

    Args:
        surcharge_result: ``SurchargeResult.model_dump()`` shape with keys
            ``surcharge_pct`` (fraction, e.g. 0.10 for 10%),
            ``surcharge_amount`` (THB), ``total`` (THB), ``capped`` (bool).

    Returns:
        Multi-line markdown table string.
    """
    pct = surcharge_result["surcharge_pct"]
    amount = surcharge_result["surcharge_amount"]
    total = surcharge_result["total"]
    base_rate = total - amount  # base rate = total - surcharge_amount
    return (
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| Base rate | {base_rate:.2f} THB |\n"
        f"| Surcharge % | {pct * 100:.2f}% |\n"
        f"| Surcharge amount | {amount:.2f} THB |\n"
        f"| Total | {total:.2f} THB |"
    )


def _render_prose_ok(state: dict) -> str:
    """Deterministic prose summary for the happy path."""
    fd = state.get("fuel_data") or {}
    rd = state.get("route_data") or {}
    sr = state.get("surcharge_result") or {}

    price = fd.get("price")
    baseline = fd.get("baseline")
    distance_km = rd.get("distance_km")
    zone = rd.get("zone")
    shipping_type = state.get("shipping_type")
    capped = bool(sr.get("capped"))

    # Direction phrase relative to baseline (if both numbers present).
    if isinstance(price, (int, float)) and isinstance(baseline, (int, float)):
        if price > baseline:
            direction = f"above the {baseline:.2f} baseline"
        elif price < baseline:
            direction = f"below the {baseline:.2f} baseline"
        else:
            direction = f"at the {baseline:.2f} baseline"
        diesel_phrase = f"Current diesel B7 is {price:.2f} THB/L ({direction})"
    else:
        diesel_phrase = "Current diesel B7 price unavailable"

    if isinstance(distance_km, (int, float)) and zone:
        route_phrase = f"on a {distance_km:.1f} km {zone} route"
    elif zone:
        route_phrase = f"on a {zone} route"
    else:
        route_phrase = "on the requested route"

    ship_phrase = f"for a {shipping_type} shipment" if shipping_type else ""
    cap_phrase = " The cap/floor was applied." if capped else ""

    prose = (
        f"{diesel_phrase} {route_phrase} {ship_phrase}.{cap_phrase}".strip()
    )
    # Squash any double spaces from the optional ship_phrase.
    while "  " in prose:
        prose = prose.replace("  ", " ")
    return f"{prose}\n\n{_FOOTER}"


def _render_prose_clarify(state: dict) -> str:
    """Friendly clarification prose listing missing fields."""
    missing = state.get("missing_fields") or []
    reason = state.get("clarification_reason") or "missing_information"
    if missing:
        fields = ", ".join(missing)
        return (
            f"I need a bit more information to calculate your surcharge. "
            f"Please provide: {fields}. ({reason})"
        )
    return (
        "I need a bit more information to calculate your surcharge. "
        f"Please provide the missing details. ({reason})"
    )


def _render_prose_partial(state: dict) -> str:
    """Partial-result prose listing failed nodes; surcharge table appended."""
    errors = state.get("errors") or []
    failed_nodes = ", ".join(
        e.get("node", "unknown") for e in errors if isinstance(e, dict)
    )
    if failed_nodes:
        return (
            f"Could not complete analysis (failed: {failed_nodes}). "
            "Here's what I found so far."
        )
    return "Could not complete analysis. Here's what I found so far."


def response_node(state: dict) -> dict:
    """Render the final user-facing payload.

    Args:
        state: Full AgentState-shaped dict.

    Returns:
        Partial state dict with::

            {
                "final_payload": {
                    "markdown": str,
                    "surcharge_result": dict | None,
                    "capped": bool,
                    "status": "ok" | "partial" | "clarify",
                },
                "reasoning_trace": [one_trace_entry],
            }
    """
    errors = state.get("errors") or []
    clarification_reason = state.get("clarification_reason")
    surcharge_result: Optional[dict] = state.get("surcharge_result")

    # Status precedence (D-10).
    if errors:
        status = "partial"
    elif clarification_reason and not surcharge_result:
        status = "clarify"
    elif surcharge_result:
        status = "ok"
    else:
        status = "clarify"

    capped = bool(surcharge_result["capped"]) if surcharge_result else False

    # Build markdown by status.
    if status == "ok":
        prose = _render_prose_ok(state)
        table = _render_table(surcharge_result)  # type: ignore[arg-type]
        markdown = f"{prose}\n\n{table}"
        if capped:
            markdown = f"{_CAP_CALLOUT}\n\n{markdown}"
    elif status == "clarify":
        markdown = _render_prose_clarify(state)
    else:  # partial
        prose = _render_prose_partial(state)
        if surcharge_result:
            table = _render_table(surcharge_result)
            markdown = f"{prose}\n\n{table}"
            if capped:
                markdown = f"{_CAP_CALLOUT}\n\n{markdown}"
        else:
            markdown = prose

    final_payload = {
        "markdown": markdown,
        "surcharge_result": surcharge_result,
        "capped": capped,
        "status": status,
    }

    prior_steps = len(state.get("reasoning_trace") or [])
    trace_entry = {
        "step": prior_steps + 1,
        "agent": "response",
        "tool": None,
        "tool_input": {"status": status},
        "tool_output": {"markdown_length": len(markdown)},
        "reasoning": f"Rendered {status} payload",
        "timestamp": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "status": "ok",
    }

    return {
        "final_payload": final_payload,
        "reasoning_trace": [trace_entry],
    }
