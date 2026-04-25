"""Graph assembly for the Express Surcharge Orchestrator (ORCH-08, ORCH-10).

Wires the five nodes (planner, fuel_agent, route_agent, pricing_agent,
response) into a LangGraph StateGraph with:
- D-03 planner-loop topology: specialists return to planner; respond is the
  only terminal edge.
- D-22 RetryPolicy on every node (max_attempts=2, exponential backoff).
- D-23 custom retry_on callable: ONLY the enumerated transient-network
  exceptions retry. ValueError, ValidationError, RuntimeError, generic
  Exception do NOT retry.
- D-24 error-sink wrappers around the four "stateful" nodes (fuel_agent,
  route_agent, planner, response) that convert non-ValueError
  Exceptions (only reached after RetryPolicy exhausts) into a state.errors
  append + next_step="respond". Pricing-Agent ValueError still bubbles
  uncaught per D-09 — Planner's clarify path picks it up on the next loop.

Source comments cite the LangChain forum thread on retry-exhaustion control
flow: https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Sequence, Type

import httpx
from google.api_core.exceptions import ResourceExhausted
from googlemaps.exceptions import HTTPError as GMapsHTTPError
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy

from backend.agent.state import AgentState
from backend.agent.nodes.planner import planner_node
from backend.agent.nodes.fuel_agent import fuel_agent_node
from backend.agent.nodes.route_agent import route_agent_node
from backend.agent.nodes.pricing_agent import pricing_agent_node
from backend.agent.nodes.response_node import response_node

__all__ = ["build_graph", "phase3_retry_on"]

logger = logging.getLogger(__name__)

# D-23: explicit allow-list. Anything not in this tuple does NOT retry.
_RETRYABLE_EXCEPTIONS: Sequence[Type[BaseException]] = (
    httpx.HTTPError,
    httpx.TimeoutException,
    asyncio.TimeoutError,
    ResourceExhausted,
    GMapsHTTPError,
)


def phase3_retry_on(exc: BaseException) -> bool:
    """D-23 compliant retry filter.

    Returns True ONLY for the enumerated transient-network exceptions.
    ValueError / pydantic.ValidationError / generic Exception fall through
    to False so they bubble immediately to the D-24 error sink (or, for
    Pricing's ValueError, all the way to the Planner per D-09).
    """
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


def _wrap_error_sink(node_name: str, node_fn):
    """D-24: convert post-retry-exhaustion Exception into state.errors + respond.

    Three exception classes are handled:
    1. ValueError: re-raised unchanged (D-09 — planner clarify path /
       graph-level halt; tests assert via pytest.raises).
    2. Retryable transient-network exceptions (phase3_retry_on True):
       re-raised so the LangGraph Pregel runtime can apply the
       RetryPolicy. After max_attempts the runtime will surface the
       last exception, which we catch on the FINAL attempt below.
    3. Non-retryable, non-ValueError exceptions: caught and converted
       into a state.errors append + next_step='respond'.

    The trick that keeps post-exhaustion routing working is the
    ``_attempt`` counter: we only convert a retryable exception to the
    error sink AFTER it has been re-raised ``max_attempts`` times. This
    matches the LangChain forum thread on retry-exhaustion control flow:
    https://forum.langchain.com/t/the-best-way-in-langgraph-to-control-flow-after-retries-exhausted/1574

    Because each Pregel task instantiates the node freshly per retry, the
    counter is stored as a function attribute keyed on the ``id`` of the
    state dict — Pregel reuses the SAME state object across retries of a
    single task, so the id is a stable proxy for "this attempt set".
    """
    _attempt_counter: dict = {}

    def _wrapped(state: dict) -> dict:
        sid = id(state)
        try:
            result = node_fn(state)
            _attempt_counter.pop(sid, None)
            return result
        except ValueError:
            _attempt_counter.pop(sid, None)
            raise
        except Exception as exc:  # noqa: BLE001 — D-24 sink is by design
            if phase3_retry_on(exc):
                attempts = _attempt_counter.get(sid, 0) + 1
                _attempt_counter[sid] = attempts
                # Re-raise on the first attempt so RetryPolicy can retry.
                # On the final attempt (after max_attempts retries), fall
                # through to the error-sink path.
                if attempts < 2:  # max_attempts in RetryPolicy
                    raise
                # Retry exhausted — convert to error sink.
                _attempt_counter.pop(sid, None)
            else:
                _attempt_counter.pop(sid, None)
            logger.warning(
                "Node %s exception sink: %s: %s",
                node_name, type(exc).__name__, exc,
            )
            return {
                "errors": [{
                    "node": node_name,
                    "exception_type": type(exc).__name__,
                    "message": str(exc),
                    "timestamp": datetime.now(timezone.utc)
                        .isoformat().replace("+00:00", "Z"),
                }],
                "next_step": "respond",
            }
    _wrapped.__name__ = node_fn.__name__  # preserve event["name"] for SSE
    return _wrapped


def _route_from_planner(state: dict) -> str:
    """Conditional-edge selector keyed on state.next_step.

    Maps the locked next_step vocabulary to graph node names. The
    search_context value (Phase-5 stub) routes to response so the user
    gets a graceful "not supported" message rather than a graph error.
    """
    ns = state.get("next_step", "respond")
    return {
        "fetch_fuel": "fuel_agent",
        "fetch_route": "route_agent",
        "calculate_price": "pricing_agent",
        "clarify": "response",
        "respond": "response",
        "search_context": "response",
    }.get(ns, "response")


def build_graph(checkpointer=None):
    """Assemble and compile the surcharge orchestrator StateGraph.

    Args:
        checkpointer: Optional LangGraph checkpointer (typically
            AsyncSqliteSaver). If None, the graph compiles without
            persistence — useful for unit tests of routing logic.

    Returns:
        CompiledStateGraph with recursion_limit=12 (D-04 belt-and-braces
        under business cap N=6) and full retry topology applied.
    """
    retry = RetryPolicy(
        max_attempts=2,
        backoff_factor=2.0,
        initial_interval=1.0,
        jitter=True,
        retry_on=phase3_retry_on,
    )

    g = StateGraph(AgentState)

    # D-24 wrapping: planner, fuel, route, response are wrapped.
    # Pricing is NOT wrapped because D-09 mandates ValueError bubbles up
    # uncaught (and the wrapper re-raises ValueError anyway, but skipping
    # the wrap removes a stack frame and makes the test failure clearer).
    g.add_node("planner", _wrap_error_sink("planner", planner_node), retry_policy=retry)
    g.add_node("fuel_agent", _wrap_error_sink("fuel_agent", fuel_agent_node), retry_policy=retry)
    g.add_node("route_agent", _wrap_error_sink("route_agent", route_agent_node), retry_policy=retry)
    g.add_node("pricing_agent", pricing_agent_node, retry_policy=retry)
    g.add_node("response", _wrap_error_sink("response", response_node), retry_policy=retry)

    g.add_edge(START, "planner")
    g.add_conditional_edges(
        "planner",
        _route_from_planner,
        {
            "fuel_agent": "fuel_agent",
            "route_agent": "route_agent",
            "pricing_agent": "pricing_agent",
            "response": "response",
        },
    )
    # D-03: specialists return to planner for next routing decision
    g.add_edge("fuel_agent", "planner")
    g.add_edge("route_agent", "planner")
    g.add_edge("pricing_agent", "planner")
    g.add_edge("response", END)

    compiled = g.compile(checkpointer=checkpointer)
    # Pitfall 4 belt-and-braces: defensive recursion limit below the
    # LangGraph default of 25 but above our business cap of 6.
    return compiled.with_config({"recursion_limit": 12})
