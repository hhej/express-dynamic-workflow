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

Status precedence (D-10, gap-3 extension 2026-05-03):
    1. state.errors non-empty             -> "partial"
    2. state.search_context populated
       AND no surcharge_result            -> "search_only" (gap-3)
    3. state.clarification_reason set
       AND no surcharge_result            -> "clarify"
    4. surcharge_result present           -> "ok"
    5. fallback                           -> "clarify"

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


def _market_context_line(state: dict) -> Optional[str]:
    """D-11 (Phase 5): "Market context: ..." prefix when search_context present.

    Returns ``None`` when ``state.search_context`` is missing/None or
    when its ``summary`` is empty/whitespace. Frontend may also render
    this from the trace panel, but emitting the prose here keeps the
    markdown self-contained for Langfuse trace inspection and any
    non-FE consumers.
    """
    sc = state.get("search_context")
    if not sc:
        return None
    summary = (sc.get("summary") or "").strip()
    if not summary:
        return None
    return f"> **Market context:** {summary}"


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

    # Phase 5 D-07: HITL deny short-circuit. When the user declined the
    # recommended surcharge at the hitl_gate (approval_decision='deny'),
    # render a 'partial' status with decline prose; do NOT include the
    # surcharge breakdown table and null out surcharge_result in the
    # final_payload so the FE knows there is no accepted recommendation.
    if state.get("approval_decision") == "deny":
        sr = state.get("surcharge_result") or {}
        total = float(sr.get("total") or 0.0)
        prose = (
            f"You declined the recommended surcharge of {total:.2f} THB. "
            "Review the inputs and adjust as needed, or ask for a different "
            "shipping type or weight."
        )
        parts = [prose]
        markdown = "\n\n".join(parts).rstrip() + f"\n\n{_FOOTER}"
        # D-11 (Phase 5): preserve Market context prefix on the deny path
        # too — provenance applies regardless of accept/decline.
        mc_line = _market_context_line(state)
        if mc_line:
            markdown = f"{mc_line}\n\n{markdown}"
        prior_steps = len(state.get("reasoning_trace") or [])
        deny_trace = {
            "step": prior_steps + 1,
            "agent": "response",
            "tool": None,
            "tool_input": {"status": "partial"},
            "tool_output": {
                "status": "partial",
                "approval_decision": "deny",
            },
            "reasoning": "User declined the recommended surcharge.",
            "timestamp": datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "status": "ok",
        }
        return {
            "final_payload": {
                "markdown": markdown,
                "surcharge_result": None,  # D-07: no breakdown on deny
                "capped": False,
                "status": "partial",
            },
            "reasoning_trace": [deny_trace],
        }

    # gap-3 fix (2026-05-03): when search_agent populated state.search_context
    # but no surcharge was computed (search-only flow), render news prose
    # instead of falling through to clarify. The Market context blockquote
    # (D-11) still prepends below; this branch supplies the body prose so
    # the user sees "Here's the latest market context" instead of the
    # misleading "I need a bit more information to calculate your surcharge"
    # that previously rendered when clarification_reason='planner_loop_budget_exhausted'
    # was set by the D-04 guard. Errors still take precedence (status='partial')
    # so a Tavily failure path that left search_context as a graceful-warn dict
    # AND populated state.errors still renders the partial-error prose.
    sc = state.get("search_context")
    sc_has_content = bool(
        sc and ((sc.get("summary") or "").strip() or sc.get("sources"))
    )

    # Status precedence (D-10, gap-3 extension).
    if errors:
        status = "partial"
    elif sc_has_content and not surcharge_result:
        status = "search_only"
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
    elif status == "search_only":
        # gap-3 fix: deterministic news prose; the Market context blockquote
        # is prepended below (D-11) so the user sees provenance + summary +
        # this prose. Sources are surfaced in the trace panel separately.
        markdown = (
            "Here's the latest market context.\n\n"
            f"{_FOOTER}"
        )
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

    # Phase 5 D-11: prepend a "Market context: <summary>" line whenever
    # state.search_context.summary is present. Sits ABOVE the cap callout
    # (provenance first, then warnings, then prose/table) so the user
    # sees the explanatory context before the rest of the breakdown.
    mc_line = _market_context_line(state)
    if mc_line:
        markdown = f"{mc_line}\n\n{markdown}"

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
