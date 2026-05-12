"""ORCH-04: Pricing Agent node.

Calls lookup_rate(...) then calculate_surcharge_tool.invoke(...), narrates the
combined result via Gemini (D-09) with a D-11 deterministic-fallback narration,
and emits ONE D-12 trace entry whose ``tool`` field is the compound name
``"lookup_rate+calculate_surcharge"`` (D-08).

D-09 contract: ``ValueError`` raised by ``lookup_rate`` (e.g. unknown
shipping_type/zone, weight outside any tier) propagates uncaught — the
Pricing Agent does NOT swallow lookup misses.

Quick 260509-uwb (Pricing Agent reasoning upgrade):
- ``PricingReasoning`` schema gains ``bullets: list[str]`` alongside the
  existing ``summary: str`` (D-04 backward compat — schema default keeps
  pre-260509 LLM emissions like ``{"summary": "..."}`` working).
- ``_compute_volatility_flag`` reads the last 7 distinct calendar days from
  ``data/raw/eppo_diesel_prices.csv`` and categorises movement as
  ``low | normal | high`` for the fuel bullet (D-03 — no new APIs; CSV is
  already the Phase 1+2 fuel data source).
- ``_build_bullets`` produces 3-5 deterministic bullets (base rate, fuel +
  volatility, traffic-only-for-bounce, news-only-when-search_context, final
  surcharge + cap/floor note). The LLM may copy or rephrase these.
- ``_deterministic_narration`` and the LLM-failure path of ``_narrate_with_llm``
  now emit the SAME bullet shape (D-11 contract preserved AND enriched).
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, ValidationError

from backend.agent.llm import get_chat_model
from backend.agent.observability import post_formula_accuracy_score
from backend.agent.prompts.pricing_agent import SYSTEM_PROMPT
from backend.agent.tools.calculate_surcharge_tool import (
    calculate_surcharge_tool,
)
from backend.agent.tools.lookup_rate import lookup_rate
from backend.agent.tools.models import (
    RateResult,
    SurchargeInput,
    SurchargeResult,
)

__all__ = ["pricing_agent_node"]

logger = logging.getLogger(__name__)

# Default 7-day volatility window source. backend/agent/nodes/pricing_agent.py
# → parents[3] resolves to the repo root, then data/raw/eppo_diesel_prices.csv.
# Tests can override by passing a tmp_path CSV directly to
# _compute_volatility_flag, or by monkeypatching the helper to a constant flag.
DEFAULT_VOLATILITY_CSV: Path = (
    Path(__file__).resolve().parents[3] / "data" / "raw" / "eppo_diesel_prices.csv"
)


class PricingReasoning(BaseModel):
    """Structured narration schema for the Pricing Agent (D-11).

    Quick 260509-uwb (D-04): kept ``summary`` for backward compat; added
    ``bullets`` for multi-step reasoning that surfaces in the trace UI.
    Default-empty ``bullets`` means pre-260509 LLM emissions of just
    ``{"summary": "..."}`` continue to parse cleanly.
    """

    summary: str = Field(description="One-sentence pricing summary")
    bullets: list[str] = Field(
        default_factory=list,
        description=(
            "3-5 short reasoning steps walking the user through base rate, "
            "fuel delta + volatility, traffic, news context, and final "
            "surcharge."
        ),
    )


def _compute_volatility_flag(
    history_csv_path: Path | str,
    current_price: float,
) -> Literal["low", "normal", "high"]:
    """Categorise diesel volatility over the last 7 distinct calendar days.

    Algorithm (per Quick 260509-uwb plan Task 1 behavior):
    - Read all dated rows from the CSV; pick the most-recent 7 distinct calendar
      days, skipping any row whose price equals ``current_price`` AND whose
      date is "today" (avoids double-counting the current point).
    - Compute ``mean_abs_delta = mean(|price[i] - price[i-1]|)`` over the window.
    - Compute ``recent_delta = abs(current_price - first_window_price)``.
    - Threshold:
        * ``recent_delta > 0.5 * mean_abs_delta`` AND ``mean_abs_delta > 0`` → ``"high"``
        * ``recent_delta < 0.2 * mean_abs_delta`` → ``"low"``
        * otherwise → ``"normal"``
    - Fewer than 2 rows OR ``mean_abs_delta == 0`` → ``"normal"`` (safe default).

    The function is intentionally pure-ish (one CSV read, no exceptions
    propagated) — file missing or malformed must NEVER crash the pricing
    agent. Tests can pass a ``tmp_path / "fixture.csv"`` to inject a known
    history; production calls use ``DEFAULT_VOLATILITY_CSV``.

    Args:
        history_csv_path: Path to a CSV with at least ``date,diesel_b7_price``
            columns (extra columns ignored). Older rows first, newer rows last.
        current_price: The current diesel price (THB/L) the agent is reasoning
            over. Used as the "now" point against the 7-day window.

    Returns:
        One of ``"low"``, ``"normal"``, ``"high"``. Never raises.
    """
    try:
        rows: list[tuple[str, float]] = []
        with open(history_csv_path, "r", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                date_str = (row.get("date") or "").strip()
                price_str = (row.get("diesel_b7_price") or "").strip()
                if not date_str or not price_str:
                    continue
                try:
                    price = float(price_str)
                except ValueError:
                    continue
                rows.append((date_str, price))
    except (OSError, csv.Error) as exc:
        logger.debug("volatility CSV read failed (%s); defaulting to 'normal'", exc)
        return "normal"

    if len(rows) < 2:
        return "normal"

    # Drop today's row only when its price coincides with current_price
    # (avoids double-counting the live data point against itself).
    today_iso = datetime.now(timezone.utc).date().isoformat()
    if rows and rows[-1][0] == today_iso and rows[-1][1] == current_price:
        rows = rows[:-1]

    if len(rows) < 2:
        return "normal"

    # Most-recent 7 distinct calendar days.
    seen_dates: set[str] = set()
    window: list[tuple[str, float]] = []
    for date_str, price in reversed(rows):
        if date_str in seen_dates:
            continue
        seen_dates.add(date_str)
        window.append((date_str, price))
        if len(window) >= 7:
            break
    window.reverse()  # oldest-first within the window

    if len(window) < 2:
        return "normal"

    deltas = [
        abs(window[i][1] - window[i - 1][1]) for i in range(1, len(window))
    ]
    if not deltas:
        return "normal"
    mean_abs_delta = sum(deltas) / len(deltas)
    if mean_abs_delta == 0:
        return "normal"

    first_window_price = window[0][1]
    recent_delta = abs(current_price - first_window_price)

    if recent_delta > 0.5 * mean_abs_delta:
        return "high"
    if recent_delta < 0.2 * mean_abs_delta:
        return "low"
    return "normal"


def _build_bullets(
    rate: RateResult,
    surcharge: SurchargeResult,
    fuel_data: dict,
    route_data: dict,
    shipping_type: str,
    volatility_flag: str,
    search_context: Optional[dict],
    origin_hub_was_unspecified: bool = False,
    origin_hub_id: str = "hq-lat-krabang",
) -> list[str]:
    """Build the deterministic bullet list (3-6 items).

    Rules per plan Task 1 action step 3 (and Phase 999.9 D-09 prepend):
    - Bullet 0 (Phase 999.9 D-09; only when origin_hub_was_unspecified):
      "Origin unspecified — defaulted to HQ Lat Krabang." landed FIRST
      so the user sees the assumption before the rate explanation.
    - Bullet 1 (always): base rate + tier + origin hub label + origin
      zone + destination zone + shipping_type. Phase 999.9 narration-
      coherence fix: surfaces the origin so the user can tell why the
      base rate differs across hubs.
    - Bullet 2 (always): diesel price vs baseline + delta_pct + volatility flag.
    - Bullet 3 (bounce only): traffic severity contribution.
    - Bullet 4 (only when search_context has non-empty summary): market context.
    - Bullet 5 (always, last): final surcharge_pct + total + cap/floor note.
    """
    from backend.agent.tools.hubs import hub_label_for, origin_zone_for

    bullets: list[str] = []

    # Phase 999.9 D-09: silent-default narration MUST land first so the
    # user sees the assumption before the rate explanation.
    if origin_hub_was_unspecified:
        bullets.append(
            "Origin unspecified — defaulted to HQ Lat Krabang."
        )

    hub_label = hub_label_for(origin_hub_id)
    origin_zone = origin_zone_for(origin_hub_id)
    bullets.append(
        f"Base rate {rate.base_rate:.2f} THB ({rate.rate_tier} tier, "
        f"from {hub_label} ({origin_zone}) to zone {route_data['zone']}, "
        f"{shipping_type})."
    )

    bullets.append(
        f"Diesel at {fuel_data['price']:.2f} THB/L vs baseline "
        f"{fuel_data['baseline']:.2f} ({fuel_data['delta_pct']:+.2%} delta, "
        f"volatility {volatility_flag} over last 7 days)."
    )

    if shipping_type == "bounce":
        bullets.append(
            f"Bangkok Metro traffic severity {route_data['traffic_severity']}/5 "
            f"adds a per-step bump on top of the fuel delta."
        )

    if search_context:
        summary = (search_context.get("summary") or "").strip()
        if summary:
            truncated = summary[:120] + ("..." if len(summary) > 120 else "")
            bullets.append(f"Market context: {truncated}")

    if surcharge.capped and surcharge.surcharge_pct >= 0:
        cap_note = " (cap applied)"
    elif surcharge.capped:
        cap_note = " (floor applied)"
    else:
        cap_note = ""
    bullets.append(
        f"Final surcharge {surcharge.surcharge_pct:.2%} = "
        f"{surcharge.surcharge_amount:.2f} THB; "
        f"total {surcharge.total:.2f} THB{cap_note}."
    )

    return bullets


def _join_bullets(bullets: list[str]) -> str:
    """Join bullets into a newline-separated ``- bullet`` markdown string."""
    return "\n".join(f"- {b}" for b in bullets if b)


def _deterministic_narration(
    rate: RateResult,
    surcharge: SurchargeResult,
    fuel_data: dict,
    route_data: dict,
    shipping_type: str,
    volatility_flag: str,
    search_context: Optional[dict],
    origin_hub_was_unspecified: bool = False,
    origin_hub_id: str = "hq-lat-krabang",
) -> str:
    """D-11 fallback narration when Gemini parsing fails.

    Quick 260509-uwb (D-02): now emits the SAME bullet shape as the LLM
    happy path (3-5 newline-joined ``- bullet`` lines), not a single
    sentence. Trace status='ok' invariant preserved.

    Phase 999.9 D-09: prepends an "Origin unspecified" bullet when
    ``origin_hub_was_unspecified`` is True (silent-default narration).
    Phase 999.9 narration-coherence fix: ``origin_hub_id`` threads to
    bullet 1 so the user sees the origin hub explicitly.
    """
    bullets = _build_bullets(
        rate,
        surcharge,
        fuel_data,
        route_data,
        shipping_type,
        volatility_flag,
        search_context,
        origin_hub_was_unspecified=origin_hub_was_unspecified,
        origin_hub_id=origin_hub_id,
    )
    return _join_bullets(bullets)


def _parse_structured(raw: str) -> PricingReasoning:
    """Parse a JSON string into PricingReasoning.

    Strips Markdown code fences Gemini sometimes emits (```json ... ```).
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return PricingReasoning.model_validate(json.loads(text))


def _narrate_with_llm(
    rate: RateResult,
    surcharge: SurchargeResult,
    fuel_data: dict,
    route_data: dict,
    shipping_type: str,
    volatility_flag: str,
    search_context: Optional[dict],
    origin_hub_was_unspecified: bool = False,
    origin_hub_id: str = "hq-lat-krabang",
) -> str:
    """Call Gemini; fall back to deterministic bullet narration on any failure (D-11).

    Quick 260509-uwb: build a deterministic bullet seed first, hand it to
    the LLM as part of the user-message JSON payload, and prefer the LLM's
    bullets when valid (3-5 items) — otherwise use the deterministic seed.
    Always returns a newline-joined ``- bullet`` markdown string.

    Phase 999.9 D-09: when ``origin_hub_was_unspecified`` is True, the
    seed bullets prepend an "Origin unspecified" bullet. If the LLM's
    bullets win, we still re-prepend the D-09 bullet so the assumption
    is never lost across the LLM hop.
    """
    seed_bullets = _build_bullets(
        rate,
        surcharge,
        fuel_data,
        route_data,
        shipping_type,
        volatility_flag,
        search_context,
        origin_hub_was_unspecified=origin_hub_was_unspecified,
        origin_hub_id=origin_hub_id,
    )

    try:
        model = get_chat_model()

        # Per plan Task 1 action step 5: pass an augmented JSON payload to
        # the LLM (rate, surcharge, fuel, route, shipping_type, volatility,
        # search_context summary, seed bullets the node already built).
        from backend.agent.tools.hubs import hub_label_for, origin_zone_for
        payload = {
            "rate": rate.model_dump(),
            "surcharge": surcharge.model_dump(),
            "fuel_data": fuel_data,
            "route_data": route_data,
            "shipping_type": shipping_type,
            "volatility_flag": volatility_flag,
            "search_context_summary": (
                (search_context or {}).get("summary") if search_context else None
            ),
            # Phase 999.9 narration-coherence: surface origin hub so the
            # LLM can keep the "from {origin} to zone {dest}" framing
            # when it rephrases seed_bullets[0/1].
            "origin": {
                "hub_id": origin_hub_id,
                "label": hub_label_for(origin_hub_id),
                "zone": origin_zone_for(origin_hub_id),
            },
            "seed_bullets": seed_bullets,
        }

        response = model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=json.dumps(payload)),
            ]
        )
        content = getattr(response, "content", response)
        if not isinstance(content, str):
            content = str(content)
        out = _parse_structured(content)

        # Prefer LLM bullets when they look reasonable (3-5 non-empty items).
        llm_bullets = [b for b in (out.bullets or []) if b and b.strip()]
        if 3 <= len(llm_bullets) <= 5:
            # Phase 999.9 D-09: re-prepend the silent-default bullet on
            # the LLM-wins branch so the assumption survives the LLM
            # hop (the LLM cannot hallucinate the prepend on its own).
            d09_bullet = "Origin unspecified — defaulted to HQ Lat Krabang."
            if origin_hub_was_unspecified and (
                not llm_bullets or llm_bullets[0] != d09_bullet
            ):
                llm_bullets = [d09_bullet] + llm_bullets
            return _join_bullets(llm_bullets)

        # LLM emitted a backward-compat {"summary": ...} only (no bullets) —
        # fall through to deterministic seed so the trace is rich, not flat.
        return _join_bullets(seed_bullets)
    except (Exception, ValidationError) as exc:  # D-11 fallback
        logger.warning(
            "pricing_agent Gemini narration failed, using deterministic fallback: %s",
            exc,
        )
        return _join_bullets(seed_bullets)


def pricing_agent_node(
    state: dict, config: Optional[RunnableConfig] = None
) -> dict:
    """Pricing Agent: rate lookup + surcharge tool + D-12 trace entry.

    Phase 5 (Plan 05-02 / OBS-03): after a successful surcharge_result
    is built, fire-and-forget ``post_formula_accuracy_score(...)`` (D-15).
    The trace_id is read from ``config["metadata"]["langfuse_trace_id"]``
    seeded by the chat handler's ``_make_config``. Auto-eval failures
    are swallowed inside ``post_formula_accuracy_score`` AND are guarded
    here by a try/except — the user response is never affected.

    Quick 260509-uwb: pricing trace ``reasoning`` becomes a multi-line
    ``- bullet`` markdown string (3-5 bullets) that walks the user through
    base rate, fuel delta + 7-day volatility flag, traffic (bounce only),
    market context (only when ``state["search_context"]`` populated), and
    the final surcharge + cap/floor note. Formula in
    ``backend/agent/tools/calculate_surcharge.py`` is unchanged (D-01).

    Args:
        state: Full AgentState-shaped dict. Required state keys:
            ``shipping_type``, ``weight_kg``, ``fuel_data.price``,
            ``route_data.zone``, ``route_data.traffic_severity``.
            Optional: ``search_context`` (Phase 5 D-11 shape) — when
            present and ``summary`` is non-empty, a market-context bullet
            is added to the trace narration.
        config: LangGraph RunnableConfig — second positional arg LangGraph
            passes when nodes declare it. Optional so the node remains
            invokable from unit tests without a config (auto-eval is
            silently skipped in that path).

    Returns:
        Partial state dict::

            {
                "surcharge_result": SurchargeResult.model_dump(),
                "reasoning_trace": [one_compound_trace_entry],
            }

    Raises:
        ValueError: Propagates from ``lookup_rate`` per D-09 (no rate found,
            invalid weight, etc.). Pricing Agent does NOT wrap this.
    """
    # Defense-in-depth (gap-4 fix from UAT 260503-qzx, 2026-05-03):
    # A misbehaving planner LLM may emit next_step="calculate_price" before
    # route_agent or fuel_agent have run. Without this guard, the subscript
    # reads below raise KeyError ('route_data' or 'fuel_data') which
    # propagates as an SSE error event with no recovery path. Catch the
    # missing-input case here, emit a D-24 error-sink entry, and route to
    # response_node so the user sees a status='partial' answer.
    # Do NOT route back to planner (loop risk with a misbehaving planner).
    route_data = state.get("route_data")
    fuel_data = state.get("fuel_data")
    if not route_data or not fuel_data:
        missing = []
        if not route_data:
            missing.append("route_data")
        if not fuel_data:
            missing.append("fuel_data")
        msg = f"missing {' and '.join(missing)}"
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prior_steps = len(state.get("reasoning_trace") or [])
        warn_trace = {
            "step": prior_steps + 1,
            "agent": "pricing_agent",
            "tool": None,
            "tool_input": None,
            "tool_output": None,
            "reasoning": (
                f"Pricing agent invoked before required inputs were populated "
                f"({msg}). Planner likely routed to calculate_price prematurely; "
                f"short-circuiting to response with a partial answer."
            ),
            "timestamp": ts,
            "status": "warn",
        }
        return {
            "errors": [{
                "node": "pricing_agent",
                "exception_type": "KeyError",
                "message": msg,
                "timestamp": ts,
            }],
            "next_step": "respond",
            "reasoning_trace": [warn_trace],
            # Quick task 260509-utd UTD-04: count this as a tool call
            # attempt — a misbehaving planner cannot bypass the per-turn
            # cap by spamming pricing without inputs. Emit +1 DELTA
            # (operator.add reducer in AgentState).
            "tool_call_count": 1,
        }

    # Phase 999.9 D-05/D-09: resolve origin hub -> origin_zone and detect
    # silent default for the narration bullet. raw_origin_hub_id captures
    # the value at entry so we know whether the D-09 narration bullet
    # should fire even after we apply the default.
    from backend.agent.tools.hubs import origin_zone_for

    raw_origin_hub_id = state.get("origin_hub_id")
    origin_hub_was_unspecified = raw_origin_hub_id is None
    origin_hub_id = raw_origin_hub_id or "hq-lat-krabang"  # D-09 default
    origin_zone = origin_zone_for(origin_hub_id)

    shipping_type = state["shipping_type"]
    weight_kg = state["weight_kg"]
    dest_zone = state["route_data"]["zone"]
    current_diesel_price = state["fuel_data"]["price"]
    traffic_severity = state["route_data"]["traffic_severity"]

    # D-09: let ValueError from lookup_rate propagate (no swallowing).
    # Phase 999.9 D-05: 4-arg signature (shipping_type, origin_zone,
    # dest_zone, weight_kg).
    rate = lookup_rate(shipping_type, origin_zone, dest_zone, weight_kg)

    surcharge_input = SurchargeInput(
        base_rate=rate.base_rate,
        current_diesel_price=current_diesel_price,
        shipping_type=shipping_type,
        traffic_severity=traffic_severity,
    )

    raw = calculate_surcharge_tool.invoke(surcharge_input.model_dump())
    if isinstance(raw, SurchargeResult):
        surcharge = raw
    elif isinstance(raw, dict):
        surcharge = SurchargeResult.model_validate(raw)
    else:
        # Pydantic-shaped object — try model_validate via dict cast.
        surcharge = SurchargeResult.model_validate(
            raw.model_dump() if hasattr(raw, "model_dump") else dict(raw)
        )

    # Quick 260509-uwb: derive volatility flag from the EPPO CSV (D-03 — no
    # new APIs) and pull search_context from existing state (Phase 5 D-11).
    volatility_flag = _compute_volatility_flag(
        DEFAULT_VOLATILITY_CSV, current_diesel_price
    )
    search_context = state.get("search_context")

    reasoning = _narrate_with_llm(
        rate,
        surcharge,
        state["fuel_data"],
        state["route_data"],
        shipping_type,
        volatility_flag,
        search_context,
        origin_hub_was_unspecified=origin_hub_was_unspecified,
        origin_hub_id=origin_hub_id,
    )

    prior_steps = len(state.get("reasoning_trace") or [])
    trace_entry = {
        "step": prior_steps + 1,
        "agent": "pricing_agent",
        "tool": "lookup_rate+calculate_surcharge",
        "tool_input": surcharge_input.model_dump(),
        "tool_output": surcharge.model_dump(),
        "reasoning": reasoning,
        "timestamp": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),
        "status": "ok",
    }

    # OBS-03: fire-and-forget formula accuracy auto-eval (D-15).
    # Reads trace_id from RunnableConfig metadata seeded by chat handler
    # (_make_config in routes/chat.py). When invoked outside the chat
    # path (unit tests, scripts) config is None → skip silently.
    try:
        metadata = (config or {}).get("metadata") or {}
        trace_id = metadata.get("langfuse_trace_id")
        if trace_id:
            post_formula_accuracy_score(
                trace_id=trace_id,
                base_rate=rate.base_rate,
                current_diesel_price=current_diesel_price,
                shipping_type=shipping_type,
                traffic_severity=int(traffic_severity),
                agent_result=surcharge.model_dump(),
            )
    except Exception as exc:  # noqa: BLE001 — D-15 fire-and-forget invariant
        logger.warning("formula_accuracy hook (non-fatal): %s", exc)

    return {
        "surcharge_result": surcharge.model_dump(),
        "reasoning_trace": [trace_entry],
        # Quick task 260509-utd UTD-04: per-turn cost-bombing counter.
        # Emit +1 DELTA (operator.add reducer in AgentState).
        "tool_call_count": 1,
    }
