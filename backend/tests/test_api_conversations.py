"""Integration tests for GET /api/conversations + GET /api/conversations/:id.

Approach mirrors ``test_api_chat.py``: monkey-patch the four LLM seams
and three tool seams BEFORE the TestClient enters the lifespan, point
``CHECKPOINT_PATH`` at a tmp-path sqlite file, and seed the checkpoints
table by issuing a real ``POST /api/chat`` request for each thread we
want to enumerate. This proves the GET endpoints work end-to-end against
the same lifespan-managed AsyncSqliteSaver the chat endpoint writes to.
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
    """Build a JSON PlannerOutput payload with sensible defaults."""
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
def app_with_seeded_thread(tmp_path, monkeypatch):
    """Spin up FastAPI app pointed at a temp sqlite checkpoint DB.

    We re-mount the four LLM seams + three tool seams on every test so
    each ``_seed_thread`` call gets a fresh planner script and the
    happy-path graph traversal completes (planner -> fetch_fuel ->
    fetch_route -> calculate_price -> respond).

    Cleanup: explicit ``monkeypatch.delenv`` + ``importlib.reload``
    pattern (mirrors ``test_api_chat.py``) so ``CHECKPOINT_PATH`` does
    not leak into ``test_checkpoint_path_default``.
    """
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "checkpoints.db"))
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
            # Extra responses cover follow-up seeds within the same fixture
            _planner_resp("fetch_fuel"),
            _planner_resp("fetch_route"),
            _planner_resp("calculate_price"),
            _planner_resp("respond"),
            _planner_resp("fetch_fuel"),
            _planner_resp("fetch_route"),
            _planner_resp("calculate_price"),
            _planner_resp("respond"),
        ),
    )
    monkeypatch.setattr(
        fuel_mod, "get_chat_model",
        _stateful_factory(
            '{"summary":"OK","trend":"above_baseline"}',
            '{"summary":"OK","trend":"above_baseline"}',
            '{"summary":"OK","trend":"above_baseline"}',
        ),
    )
    monkeypatch.setattr(
        route_mod, "get_chat_model",
        _stateful_factory(
            '{"summary":"OK","traffic_label":"moderate"}',
            '{"summary":"OK","traffic_label":"moderate"}',
            '{"summary":"OK","traffic_label":"moderate"}',
        ),
    )
    monkeypatch.setattr(
        pricing_mod, "get_chat_model",
        _stateful_factory(
            '{"summary":"Total 132 THB"}',
            '{"summary":"Total 132 THB"}',
            '{"summary":"Total 132 THB"}',
        ),
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

    monkeypatch.delenv("CHECKPOINT_PATH", raising=False)
    importlib.reload(backend.config)
    importlib.reload(backend.api.main)


def _seed_thread(
    client: TestClient,
    thread_id: str,
    message: str = "Surcharge for 15kg Bounce Bangkok to Nonthaburi",
):
    """Drive POST /api/chat to completion so the AsyncSqliteSaver writes
    a checkpoint row for ``thread_id``."""
    with client.stream(
        "POST", "/api/chat",
        json={"message": message, "thread_id": thread_id},
    ) as r:
        # Exhaust the SSE stream to ensure the lifespan flushes the final
        # checkpoint to disk before we query the GET endpoints.
        for _ in r.iter_text():
            pass


def test_lists_conversations_desc(app_with_seeded_thread):
    """Two seeded threads return newest-first with full summary fields."""
    with TestClient(app_with_seeded_thread) as client:
        _seed_thread(client, "thread-A")
        _seed_thread(client, "thread-B")

        resp = client.get("/api/conversations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

        tids = [d["thread_id"] for d in data]
        assert "thread-A" in tids
        assert "thread-B" in tids

        # Most recently seeded thread (B) should be first.
        assert data[0]["thread_id"] == "thread-B"

        for entry in data:
            assert "thread_id" in entry
            assert "last_updated" in entry
            assert "first_message_preview" in entry


def test_returns_thread_state(app_with_seeded_thread):
    """Replaying a known thread returns the full AgentState snapshot."""
    with TestClient(app_with_seeded_thread) as client:
        _seed_thread(client, "thread-X")

        resp = client.get("/api/conversations/thread-X")
        assert resp.status_code == 200
        data = resp.json()

        assert data["thread_id"] == "thread-X"
        assert isinstance(data["messages"], list)
        assert len(data["messages"]) >= 1
        assert isinstance(data["reasoning_trace"], list)
        # Surcharge result populated for happy-path query.
        assert data["surcharge_result"] is not None


def test_404_unknown_thread(app_with_seeded_thread):
    """An unknown thread_id returns HTTP 404."""
    with TestClient(app_with_seeded_thread) as client:
        resp = client.get("/api/conversations/no-such-thread")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 7 D-05 / D-06 / D-07 — message_id attached on LAST assistant per turn
# ---------------------------------------------------------------------------


def test_get_conversation_attaches_message_id_to_last_assistant(
    app_with_seeded_thread,
):
    """Phase 7 D-05/D-07: GET /api/conversations/:id stamps message_id
    on the LAST assistant message of each turn. Format: '{thread_id}-{turn_idx}'.
    """
    with TestClient(app_with_seeded_thread) as client:
        _seed_thread(client, "thread-msgid")

        resp = client.get("/api/conversations/thread-msgid")
        assert resp.status_code == 200
        data = resp.json()

    # Every turn = 1 user message; this seed produces 1 turn.
    assistants = [m for m in data["messages"] if m.get("role") == "assistant"]
    assert len(assistants) >= 1, (
        f"expected at least one assistant message; got messages={data['messages']!r}"
    )
    # The LAST assistant of each turn must carry message_id.
    last_assistant = assistants[-1]
    assert "message_id" in last_assistant, (
        "LAST assistant of turn must carry message_id (Phase 7 D-05/D-07); "
        f"got keys: {list(last_assistant.keys())}"
    )
    assert last_assistant["message_id"] == "thread-msgid-0"


def test_get_conversation_message_id_user_messages_have_no_field(
    app_with_seeded_thread,
):
    """Phase 7 D-06: user messages have NO message_id field (silent absence).

    Per D-06 the field absence is the natural signal — user rows have no
    feedback affordance. A parallel array OR an explicit null would force
    the FE to special-case; field-absence is the cleanest contract.
    """
    with TestClient(app_with_seeded_thread) as client:
        _seed_thread(client, "thread-userrows")

        resp = client.get("/api/conversations/thread-userrows")
        assert resp.status_code == 200
        data = resp.json()

    users = [m for m in data["messages"] if m.get("role") == "user"]
    assert len(users) >= 1, "seed must have produced at least one user message"
    for u in users:
        assert "message_id" not in u, (
            "user messages must not carry message_id (Phase 7 D-06); "
            f"got user message: {u!r}"
        )
