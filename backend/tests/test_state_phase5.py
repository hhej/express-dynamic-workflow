"""Phase 5 AgentState extensions (D-07 approval_decision, D-11 search_context)."""
from __future__ import annotations
from typing import get_type_hints

from backend.agent.state import AgentState


def test_agent_state_has_approval_decision_field():
    hints = get_type_hints(AgentState)
    assert "approval_decision" in hints, "D-07 approval_decision missing"


def test_agent_state_has_search_context_field():
    hints = get_type_hints(AgentState)
    assert "search_context" in hints, "D-11 search_context missing"


def test_existing_reducers_still_present():
    """Phase 2 Pitfall 1 + Phase 3 D-05 — operator.add on reasoning_trace and errors is load-bearing.

    Note: backend/agent/state.py uses ``from __future__ import annotations`` so
    raw ``__annotations__`` entries are ForwardRefs without ``__metadata__``.
    ``get_type_hints(..., include_extras=True)`` resolves the strings into
    real ``Annotated`` aliases that preserve the reducer metadata.
    """
    import operator

    hints = get_type_hints(AgentState, include_extras=True)
    rt_meta = getattr(hints["reasoning_trace"], "__metadata__", ())
    errs_meta = getattr(hints["errors"], "__metadata__", ())
    assert rt_meta and rt_meta[0] is operator.add, (
        "reasoning_trace lost its operator.add reducer (Phase 2 Pitfall 1)"
    )
    assert errs_meta and errs_meta[0] is operator.add, (
        "errors lost its operator.add reducer (Phase 3 D-05)"
    )
