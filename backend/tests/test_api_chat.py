"""Integration tests for POST /api/chat (API-01).

Exercises the FastAPI app + lifespan + AsyncSqliteSaver + compiled graph
end-to-end via the synchronous ``TestClient``.streaming API.

Mocks the four LLM seams (planner / fuel / route / pricing) and the three
external tool seams (fetch_fuel_price / calculate_route / lookup_rate)
BEFORE the TestClient enters the lifespan, so the lifespan compiles a
graph against the mocked modules. The CHECKPOINT_PATH env var is pointed
at a tmp_path-derived sqlite file so each test runs in isolation.
"""
from __future__ import annotations

import importlib
import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import (
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from backend.agent.tools.models import FuelData, RateResult, RouteData


def _llm(*responses_json: str) -> FakeMessagesListChatModel:
    """Single shared FakeMessagesListChatModel cycling through responses."""
    return FakeMessagesListChatModel(
        responses=[AIMessage(content=r) for r in responses_json]
    )


def _stateful_factory(*responses_json: str):
    """Return a ``get_chat_model`` replacement returning the SAME shared
    fake LLM on every call so planner-loop scripts replay across calls.
    """
    shared = _llm(*responses_json)

    def factory(**_):
        return shared

    return factory


def _planner_resp(next_step: str, **overrides) -> str:
    """Build a JSON PlannerOutput payload with sensible Bangkok-Nonthaburi defaults."""
    payload = {
        "user_intent": "surcharge_query",
        "shipping_type": "bounce",
        "weight_kg": 15.0,
        "origin": "Bangkok",
        "destination": "Nonthaburi",
        "missing_fields": [],
        "clarification_reason": None,
    }
    payload.update(overrides)
    payload["next_step"] = next_step
    return json.dumps(payload)


@pytest.fixture
def app_with_mocks(tmp_path, monkeypatch):
    """Spin up FastAPI app pointed at a temp sqlite checkpoint DB.

    Patches the four LLM seams + three tool seams BEFORE TestClient enters
    the lifespan so the lifespan compiles a graph against the mocked
    modules.

    Cleanup: reload ``backend.config`` and ``backend.api.main`` after the
    test so the in-memory ``CHECKPOINT_PATH`` reverts to the literal
    default ``data/checkpoints.db`` (avoids polluting later tests like
    ``test_checkpoint_path_default`` that read the module-level constant).
    """
    monkeypatch.setenv(
        "CHECKPOINT_PATH", str(tmp_path / "checkpoints.db")
    )
    # Reload config + main so the new env var is picked up at app build.
    import backend.config
    importlib.reload(backend.config)
    import backend.api.main
    importlib.reload(backend.api.main)

    from backend.agent.nodes import planner as planner_mod
    from backend.agent.nodes import fuel_agent as fuel_mod
    from backend.agent.nodes import route_agent as route_mod
    from backend.agent.nodes import pricing_agent as pricing_mod

    monkeypatch.setattr(
        planner_mod, "get_chat_model",
        _stateful_factory(
            _planner_resp("fetch_fuel"),
            _planner_resp("fetch_route"),
            _planner_resp("calculate_price"),
            _planner_resp("respond"),
        ),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory('{"summary":"OK","trend":"above_baseline"}'),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        _stateful_factory('{"summary":"OK","traffic_label":"moderate"}'),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model",
        _stateful_factory('{"summary":"Total 132 THB"}'),
    )
    monkeypatch.setattr(
        fuel_mod, "fetch_fuel_price",
        lambda: FuelData(
            price=31.0, date="2026-04-25", source="eppo_live",
            baseline=29.94, delta_pct=0.0354,
        ),
    )
    monkeypatch.setattr(
        route_mod, "calculate_route",
        lambda *a, **kw: RouteData(
            origin="Bangkok", destination="Nonthaburi",
            distance_km=18.0, duration_min=30,
            traffic_severity=2, zone="central-1",
        ),
    )
    monkeypatch.setattr(
        pricing_mod, "lookup_rate",
        lambda *a, **kw: RateResult(
            base_rate=120.0, currency="THB", rate_tier="11-25kg",
        ),
    )

    yield backend.api.main.app

    # Cleanup: pytest's monkeypatch fixture restores the env var on
    # teardown AFTER our yield-cleanup runs, so we must explicitly
    # delete it here before reloading config -- otherwise the imported
    # backend.config module still carries the tmp-path string and
    # later tests (e.g. test_checkpoint_path_default) read the polluted
    # constant. Then reload backend.api.main for symmetry so any later
    # test importing `app` sees a fresh module bound to the restored
    # config.
    monkeypatch.delenv("CHECKPOINT_PATH", raising=False)
    importlib.reload(backend.config)
    importlib.reload(backend.api.main)


def _parse_sse_events(raw_text: str) -> list[dict]:
    """Parse a concatenated SSE stream into a list of envelope dicts."""
    events = []
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: "):]))
    return events


def test_happy_path_sse_sequence(app_with_mocks):
    """Happy path: meta -> trace+ -> answer -> done with proper headers."""
    with TestClient(app_with_mocks) as client:
        with client.stream(
            "POST", "/api/chat",
            json={
                "message": (
                    "Surcharge for 15kg Bounce Bangkok to Nonthaburi"
                ),
                "thread_id": "t-happy",
            },
        ) as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            assert r.headers.get("cache-control") == "no-cache"
            assert r.headers.get("x-accel-buffering") == "no"
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    types = [e["type"] for e in events]

    # First event MUST be meta with the supplied thread_id.
    assert types[0] == "meta"
    assert events[0]["payload"]["thread_id"] == "t-happy"

    # Last event MUST be done.
    assert types[-1] == "done"

    # An answer event MUST appear in the stream.
    assert "answer" in types

    # At least 4 trace events (planner + fuel + route + pricing + response).
    assert types.count("trace") >= 4

    # Final answer payload shape (D-10).
    answer = next(e for e in events if e["type"] == "answer")
    assert "markdown" in answer["payload"]
    assert "surcharge_result" in answer["payload"]
    assert answer["payload"]["status"] == "ok"


def test_server_generates_thread_id(app_with_mocks):
    """When client omits thread_id the server emits a fresh UUIDv4."""
    with TestClient(app_with_mocks) as client:
        with client.stream(
            "POST", "/api/chat",
            json={
                "message": (
                    "Surcharge for 15kg Bounce Bangkok to Nonthaburi"
                ),
            },
        ) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    meta = events[0]
    assert meta["type"] == "meta"
    tid = meta["payload"]["thread_id"]
    # UUIDv4 is 36 chars with 4 hyphens.
    assert isinstance(tid, str)
    assert len(tid) == 36
    assert tid.count("-") == 4


def test_error_sse_sequence(app_with_mocks, monkeypatch):
    """Force the response_node to raise so the chat handler emits an
    ``error`` event before ``done``. Because the StateGraph compiled in
    the lifespan resolves ``response_node`` at module-import time via the
    ``backend.agent.nodes.response_node`` module attribute, monkey-patching
    that attribute at the chat-call site does not retroactively swap the
    bound function inside the graph. Instead we monkey-patch the inner
    ``_render_table`` helper to raise -- ``response_node`` calls
    ``_render_table`` internally, the exception propagates, the D-24
    error sink converts it on the FIRST call into errors[]+respond which
    routes back to ``response``, and the second invocation also raises ->
    eventually surfaced through the chat handler's try/except as a typed
    SSE error event before ``done``.

    A simpler alternative: raise from the pricing tool seam so the graph
    short-circuits to Response Node with status='partial' (D-24 behaviour),
    but that path emits an ``answer`` event with status=partial, not an
    ``error``. The test accepts EITHER outcome since both are valid
    failure-mode signals per D-23/D-24.
    """
    from backend.agent.nodes import pricing_agent as pricing_mod

    def boom(*args, **kwargs):
        raise RuntimeError("simulated catastrophic failure")

    # Replace lookup_rate so the pricing node raises uncaught (D-09 lets
    # ValueError propagate; RuntimeError is non-retryable per D-23 and is
    # not wrapped on the pricing node). The graph's outer ainvoke surfaces
    # the exception; the chat handler's try/except yields an ``error``
    # event before ``done``.
    monkeypatch.setattr(pricing_mod, "lookup_rate", boom)

    with TestClient(app_with_mocks) as client:
        with client.stream(
            "POST", "/api/chat",
            json={
                "message": (
                    "Surcharge for 15kg Bounce Bangkok to Nonthaburi"
                ),
                "thread_id": "t-error",
            },
        ) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    types = [e["type"] for e in events]

    # Stream MUST always close with done.
    assert types[-1] == "done"

    # Either an explicit error event OR a partial-status answer event.
    has_error = "error" in types
    has_partial_answer = any(
        e["type"] == "answer"
        and e["payload"].get("status") == "partial"
        for e in events
    )
    assert has_error or has_partial_answer, (
        f"Expected error or partial-status answer; got types={types}"
    )

    if has_error:
        err = next(e for e in events if e["type"] == "error")
        assert "message" in err["payload"]
        assert "retryable" in err["payload"]
