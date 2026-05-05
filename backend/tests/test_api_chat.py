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


def test_chat_handler_threads_trace_id_into_config(app_with_mocks, monkeypatch):
    """Plan 05-02 canary: verify the trace_id seeded for the turn appears
    in the config the chat handler uses to invoke the graph.

    This canary is intentionally loose — it does NOT assert on the SSE
    stream contents (those are covered by happy-path / error tests
    above). It only spies on ``_make_config`` to confirm the chat
    handler builds the Plan 05-02 config shape. Tolerant of clarify /
    error stream paths so unrelated graph-routing breakage cannot mask
    a regression in _make_config wiring.
    """
    from backend.api.routes import chat as chat_mod

    captured: dict = {"config": None}
    original_make = chat_mod._make_config

    def spy_make(thread_id, turn_idx):
        cfg = original_make(thread_id, turn_idx)
        captured["config"] = cfg
        return cfg

    monkeypatch.setattr(chat_mod, "_make_config", spy_make)

    with TestClient(app_with_mocks) as client:
        with client.stream(
            "POST", "/api/chat",
            json={
                "message": (
                    "Surcharge for 15kg Bounce Bangkok to Nonthaburi"
                ),
                "thread_id": "t-trace-id",
            },
        ) as r:
            assert r.status_code == 200
            # Drain the stream so the handler runs to completion.
            for _ in r.iter_text():
                pass

    assert captured["config"] is not None
    # Plan 05-02 contract: deterministic 32-hex langfuse_trace_id present.
    metadata = captured["config"]["metadata"]
    assert "langfuse_trace_id" in metadata
    trace_id = metadata["langfuse_trace_id"]
    assert isinstance(trace_id, str)
    assert len(trace_id) == 32
    assert all(ch in "0123456789abcdef" for ch in trace_id)
    # Session id mirrors thread_id.
    assert metadata["langfuse_session_id"] == "t-trace-id"
    # Tags include the express-surcharge marker + per-turn tag.
    assert "express-surcharge" in metadata["langfuse_tags"]
    assert any(tag.startswith("turn-") for tag in metadata["langfuse_tags"])


# ---------------------------------------------------------------------------
# Phase 5 ORCH-09 — HITL approval gate SSE event + Command(resume) handler
# ---------------------------------------------------------------------------


def _make_stub_graph(astream_events, *, snapshot_next=(), interrupt_value=None):
    """Build a MagicMock graph with controllable astream_events + aget_state.

    Args:
        astream_events: async generator function (graph.astream_events stub).
        snapshot_next: tuple returned by snapshot.next; non-empty means paused.
        interrupt_value: value carried inside snapshot.tasks[0].interrupts[0].

    Returns:
        Stub graph object. Caller is responsible for installing it on
        ``app.state.graph`` AFTER the TestClient enters the lifespan
        (lifespan replaces ``app.state.graph`` with the real compiled
        graph, so pre-lifespan installation is overwritten).
    """
    from unittest.mock import AsyncMock, MagicMock

    snapshot = MagicMock()
    snapshot.next = snapshot_next
    if snapshot_next:
        interrupt_obj = MagicMock()
        interrupt_obj.value = interrupt_value or {}
        task = MagicMock()
        task.interrupts = [interrupt_obj]
        snapshot.tasks = [task]
    else:
        snapshot.tasks = []

    graph_mock = MagicMock()
    graph_mock.astream_events = astream_events
    graph_mock.aget_state = AsyncMock(return_value=snapshot)
    return graph_mock


def test_sse_event_type_includes_approval_required():
    """D-06 sixth event type: ``approval_required`` is in the EventType Literal."""
    from backend.api.sse import EventType
    assert "approval_required" in EventType.__args__


def test_chat_emits_approval_required_when_paused(app_with_mocks, monkeypatch):
    """Pitfall 2: paused stream emits approval_required and NOT done after it.

    Stubs ``graph.astream_events`` to yield no events (the gate already paused
    before any node-end fired) and ``graph.aget_state`` to indicate the run
    is paused (snapshot.next non-empty) with the interrupt payload from
    hitl_gate_node (D-05 shape).
    """
    from backend.api.routes import chat as chat_mod
    from unittest.mock import AsyncMock

    async def fake_astream_events(*args, **kwargs):
        # Empty async generator — nothing emitted before the pause.
        if False:
            yield  # pragma: no cover  # makes function an async gen

    stub = _make_stub_graph(
        fake_astream_events,
        snapshot_next=("response",),
        interrupt_value={
            "type": "approval_required",
            "surcharge_result": {
                "total": 715.0,
                "surcharge_pct": 0.10,
                "surcharge_amount": 65.0,
                "capped": False,
            },
            "threshold": 500.0,
        },
    )
    # Bypass _next_turn_idx — the stub graph's aget_state returns a MagicMock
    # whose .values is also a MagicMock (not a dict), so the handler's helper
    # would error otherwise.
    monkeypatch.setattr(chat_mod, "_next_turn_idx", AsyncMock(return_value=0))

    with TestClient(app_with_mocks) as client:
        # Install stub AFTER lifespan enters — lifespan replaces app.state.graph
        # with the real compiled graph, so pre-lifespan installation is lost.
        app_with_mocks.state.graph = stub
        with client.stream(
            "POST", "/api/chat",
            json={"message": "expensive shipment", "thread_id": "tid-pause"},
        ) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    types = [e["type"] for e in events]

    # Exactly one approval_required event present.
    assert types.count("approval_required") == 1
    ap = next(e for e in events if e["type"] == "approval_required")
    assert ap["payload"]["surcharge_result"]["total"] == 715.0
    assert ap["payload"]["threshold"] == 500.0
    assert ap["payload"]["thread_id"] == "tid-pause"

    # Pitfall 2: approval_required must NOT be followed by done in the
    # same stream (the frontend keeps Approve/Deny buttons live).
    ap_idx = types.index("approval_required")
    assert "done" not in types[ap_idx + 1:], (
        f"done emitted after approval_required (Pitfall 2): types={types}"
    )


def test_chat_resume_with_approve_renders_status_ok(app_with_mocks, monkeypatch):
    """D-06 resume with approve=True emits status='ok' answer."""
    from backend.api.routes import chat as chat_mod
    from unittest.mock import AsyncMock

    async def fake_astream_events(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "response",
            "data": {"output": {
                "final_payload": {
                    "markdown": "ok rendered with table",
                    "status": "ok",
                    "surcharge_result": {
                        "total": 715.0, "surcharge_pct": 0.10,
                        "surcharge_amount": 65.0, "capped": False,
                    },
                    "capped": False,
                },
            }},
        }

    stub = _make_stub_graph(fake_astream_events, snapshot_next=())
    monkeypatch.setattr(chat_mod, "_next_turn_idx", AsyncMock(return_value=1))

    with TestClient(app_with_mocks) as client:
        app_with_mocks.state.graph = stub
        with client.stream(
            "POST", "/api/chat",
            json={"thread_id": "tid-approve", "approve": True},
        ) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    types = [e["type"] for e in events]
    assert "answer" in types
    answer = next(e for e in events if e["type"] == "answer")
    assert answer["payload"]["status"] == "ok"
    assert answer["payload"]["surcharge_result"] is not None
    # Resume path closes the stream normally with done.
    assert types[-1] == "done"


def test_chat_resume_with_deny_renders_status_partial(
    app_with_mocks, monkeypatch
):
    """D-07 deny: resume with approve=False emits status='partial' + 'declined'
    prose; surcharge_result null in the answer payload."""
    from backend.api.routes import chat as chat_mod
    from unittest.mock import AsyncMock

    async def fake_astream_events(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "response",
            "data": {"output": {
                "final_payload": {
                    "markdown": "You declined the recommended surcharge.",
                    "status": "partial",
                    "surcharge_result": None,
                    "capped": False,
                },
            }},
        }

    stub = _make_stub_graph(fake_astream_events, snapshot_next=())
    monkeypatch.setattr(chat_mod, "_next_turn_idx", AsyncMock(return_value=1))

    with TestClient(app_with_mocks) as client:
        app_with_mocks.state.graph = stub
        with client.stream(
            "POST", "/api/chat",
            json={"thread_id": "tid-deny", "approve": False},
        ) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    answer = next(e for e in events if e["type"] == "answer")
    assert answer["payload"]["status"] == "partial"
    assert answer["payload"]["surcharge_result"] is None
    assert "declined" in answer["payload"]["markdown"].lower()


def test_chat_resume_reuses_make_config_helper(app_with_mocks, monkeypatch):
    """Pitfall 1: resume path reuses _make_config so Langfuse callbacks +
    metadata are preserved across the pause."""
    from backend.api.routes import chat as chat_mod
    from unittest.mock import AsyncMock

    captured = {"calls": 0, "configs": []}
    original = chat_mod._make_config

    def spy(thread_id, turn_idx):
        cfg = original(thread_id, turn_idx)
        captured["calls"] += 1
        captured["configs"].append(cfg)
        return cfg

    monkeypatch.setattr(chat_mod, "_make_config", spy)

    async def fake_astream_events(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "response",
            "data": {"output": {
                "final_payload": {
                    "markdown": "resumed",
                    "status": "ok",
                    "surcharge_result": {
                        "total": 715.0, "surcharge_pct": 0.10,
                        "surcharge_amount": 65.0, "capped": False,
                    },
                    "capped": False,
                },
            }},
        }

    stub = _make_stub_graph(fake_astream_events, snapshot_next=())
    monkeypatch.setattr(chat_mod, "_next_turn_idx", AsyncMock(return_value=1))

    with TestClient(app_with_mocks) as client:
        app_with_mocks.state.graph = stub
        with client.stream(
            "POST", "/api/chat",
            json={"thread_id": "tid-config", "approve": True},
        ) as r:
            assert r.status_code == 200
            for _ in r.iter_text():
                pass

    assert captured["calls"] >= 1
    cfg = captured["configs"][0]
    # Resume path reuses the SAME helper, so the metadata shape matches
    # _make_config's contract (thread_id mirrors session, deterministic
    # 32-hex trace_id present).
    assert cfg["configurable"]["thread_id"] == "tid-config"
    md = cfg["metadata"]
    assert md["langfuse_session_id"] == "tid-config"
    assert isinstance(md["langfuse_trace_id"], str)
    assert len(md["langfuse_trace_id"]) == 32


# ---------------------------------------------------------------------------
# Phase 7 D-01 / D-02 — message_id stamped on SSE answer payload
# ---------------------------------------------------------------------------

import re


def test_happy_path_answer_payload_contains_message_id(app_with_mocks):
    """Phase 7 D-01: every SSE answer payload carries message_id = '{thread_id}-{turn_idx}'.

    Drift-prevention sibling for the Vitest+MSW round-trip in Plan 07-02.
    Asserts the BE-stamped string is exactly what the frontend will read
    and POST back to /api/feedback.
    """
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
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    answer = next(e for e in events if e["type"] == "answer")
    assert "message_id" in answer["payload"], (
        "answer payload must carry message_id (Phase 7 D-01); "
        f"got payload keys: {list(answer['payload'].keys())}"
    )
    assert answer["payload"]["message_id"] == "t-happy-0"


def test_answer_message_id_matches_feedback_regex(app_with_mocks):
    """Phase 7: BE-stamped message_id must parse cleanly through feedback.py regex.

    Reproduces the exact contract feedback.py enforces: regex match
    '^(.+)-(\\d+)$' AND parsed thread_id == request thread_id. If this
    assertion fails, the FE click would 400 even though the FE wires
    message_id through correctly — single chokepoint.
    """
    with TestClient(app_with_mocks) as client:
        with client.stream(
            "POST", "/api/chat",
            json={
                "message": (
                    "Surcharge for 15kg Bounce Bangkok to Nonthaburi"
                ),
                "thread_id": "t-regex",
            },
        ) as r:
            assert r.status_code == 200
            body = "".join(chunk for chunk in r.iter_text())

    events = _parse_sse_events(body)
    answer = next(e for e in events if e["type"] == "answer")
    message_id = answer["payload"]["message_id"]
    m = re.match(r"^(.+)-(\d+)$", message_id)
    assert m is not None, (
        f"message_id {message_id!r} must match feedback.py regex "
        f"'^(.+)-(\\d+)$'"
    )
    assert m.group(1) == "t-regex"
    assert m.group(2) == "0"

