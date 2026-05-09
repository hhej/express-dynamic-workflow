"""Post-pricing guard node — Quick task 260509-utd Task 2 (UTD-03).

Sits between ``pricing_agent`` and ``hitl_gate``. Re-validates the
``surcharge_result`` produced by pricing against the invariants from
``backend.config`` and ``backend.agent.tools.calculate_surcharge``.
This is pure Python (no LLM call) and never re-runs the surcharge
formula — re-execution risks divergence if upstream inputs were already
mutated (RESEARCH §Anti-Patterns).

Why a guard if ``calculate_surcharge`` already enforces these invariants?
Defense-in-depth (RESEARCH §Pattern 2):

- A future LLM-generated SurchargeResult that bypasses the pure
  function still trips here.
- Tool-output corruption / state mutation by other nodes is caught.
- Successful indirect-injection that tricks the planner into emitting
  a bad shipping_type still gets blocked at the schema check.

Failure mode: ``next_step='respond'`` plus a single trace entry tagged
``agent='guard_output'`` (Pitfall 5: NEVER 'planner'). ``response_node``
then renders the canonical ``REFUSAL_COPY`` with status='guard_failed'.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from backend.config import (
    SHIPPING_MULTIPLIERS,
    SURCHARGE_CAP,
    SURCHARGE_FLOOR,
)

__all__ = ["guard_output_node", "_route_from_guard_output"]


_REQUIRED_FIELDS = ("surcharge_pct", "surcharge_amount", "total", "capped")


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate(state: dict) -> List[str]:
    """Return the list of invariant violations; empty list when valid."""
    violations: List[str] = []
    sr = state.get("surcharge_result") or {}
    pct = sr.get("surcharge_pct")
    total = sr.get("total")
    amt = sr.get("surcharge_amount")
    st = state.get("shipping_type")
    w = state.get("weight_kg")

    if pct is None or not (SURCHARGE_FLOOR <= pct <= SURCHARGE_CAP):
        violations.append(
            f"surcharge_pct {pct} outside [{SURCHARGE_FLOOR}, {SURCHARGE_CAP}]"
        )
    if total is None or total <= 0:
        violations.append(f"total {total} not > 0")
    if amt is None:
        violations.append("surcharge_amount missing")
    if st not in SHIPPING_MULTIPLIERS:
        violations.append(f"shipping_type '{st}' not whitelisted")
    if w is None or w <= 0:
        violations.append(f"weight_kg {w} not > 0")

    # Schema completeness check — surfaces any future drift between the
    # SurchargeResult model and what pricing actually emits.
    for key in _REQUIRED_FIELDS:
        if key not in sr:
            violations.append(f"missing field '{key}'")

    return violations


def guard_output_node(state: dict) -> dict:
    """Pure-Python invariant validator for ``surcharge_result``.

    Args:
        state: Full AgentState-shaped dict. Reads ``surcharge_result``,
            ``shipping_type``, ``weight_kg``.

    Returns:
        Partial state dict. On the allow path: just the verdict (no
        ``reasoning_trace``, no ``next_step`` rewrite). On the refused
        path: ``next_step='respond'`` plus a single trace entry tagged
        ``agent='guard_output'``.
    """
    violations = _validate(state)
    refused = bool(violations)

    verdict = {
        "layer": "output",
        "category": "unsafe_output" if refused else "allow",
        "refused": refused,
        "violations": violations,
    }

    if not refused:
        # Zero-overhead allow path — mirrors hitl_gate low-value bypass.
        return {"guard_decision": verdict}

    trace_entry = {
        "step": (len(state.get("reasoning_trace") or []) + 1),
        "agent": "guard_output",  # Pitfall 5: NEVER tag as 'planner'
        "tool": None,
        "tool_input": {
            "shipping_type": state.get("shipping_type"),
            "weight_kg": state.get("weight_kg"),
            "surcharge_result": state.get("surcharge_result"),
        },
        "tool_output": {
            "refused": True,
            "violations": violations,
        },
        "reasoning": (
            f"Output guard tripped on {len(violations)} invariant violation"
            f"{'s' if len(violations) != 1 else ''}: "
            f"{'; '.join(violations)}"
        ),
        "timestamp": _ts(),
        "status": "warn",
    }
    return {
        "next_step": "respond",
        "guard_decision": verdict,
        "reasoning_trace": [trace_entry],
    }


def _route_from_guard_output(state: dict) -> str:
    """Conditional-edge selector for guard_output -> hitl_gate|response."""
    gd = state.get("guard_decision") or {}
    return "response" if gd.get("refused") else "hitl_gate"
