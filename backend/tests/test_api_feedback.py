"""API-05 / OBS-02 — POST /api/feedback tests."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app


@pytest.fixture
def client():
    """TestClient with the FastAPI app (no real Langfuse keys required)."""
    return TestClient(app)


def test_feedback_posts_score(monkeypatch, client):
    """D-16: POST {thread_id, message_id, score: 'up'} → create_score(value=1)."""
    captured: dict = {}
    fake = MagicMock()

    def fake_create_score(**kw):
        captured.update(kw)

    fake.create_score = fake_create_score
    # Patch the helpers in the routes.feedback module (re-imported namespace).
    from backend.api.routes import feedback as fb_mod

    monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(fb_mod, "seed_trace_id", lambda tid, ti: f"trace-{tid}-{ti}")
    resp = client.post(
        "/api/feedback",
        json={
            "thread_id": "abc",
            "message_id": "abc-0",
            "score": "up",
            "reason": "useful answer",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["delivered"] is True
    assert body["trace_id"] == "trace-abc-0"
    assert captured["trace_id"] == "trace-abc-0"
    assert captured["name"] == "user_feedback"
    assert captured["value"] == 1
    assert captured["comment"] == "useful answer"


def test_feedback_score_down_maps_to_negative_one(monkeypatch, client):
    from backend.api.routes import feedback as fb_mod

    captured: dict = {}
    fake = MagicMock()
    fake.create_score = lambda **kw: captured.update(kw)
    monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(fb_mod, "seed_trace_id", lambda tid, ti: "x")
    resp = client.post(
        "/api/feedback",
        json={"thread_id": "t", "message_id": "t-3", "score": "down"},
    )
    assert resp.status_code == 200
    assert captured["value"] == -1


def test_feedback_no_op_without_keys(monkeypatch, client):
    """D-13 graceful no-op: 200 with delivered=false."""
    from backend.api.routes import feedback as fb_mod

    monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: None)
    resp = client.post(
        "/api/feedback",
        json={"thread_id": "t", "message_id": "t-0", "score": "up"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["delivered"] is False
    assert "langfuse_disabled" in body["reason"]


def test_feedback_malformed_message_id_returns_400(client):
    resp = client.post(
        "/api/feedback",
        json={
            "thread_id": "t",
            "message_id": "no-numeric-suffix-here",
            "score": "up",
        },
    )
    assert resp.status_code == 400


def test_feedback_thread_mismatch_returns_400(client):
    """defense-in-depth: body thread_id and message_id parsed thread_id must match."""
    resp = client.post(
        "/api/feedback",
        json={"thread_id": "wrong", "message_id": "actual-0", "score": "up"},
    )
    assert resp.status_code == 400


def test_feedback_langfuse_error_returns_502(monkeypatch, client):
    from backend.api.routes import feedback as fb_mod

    fake = MagicMock()
    fake.create_score.side_effect = RuntimeError("network timeout")
    monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(fb_mod, "seed_trace_id", lambda tid, ti: "x")
    resp = client.post(
        "/api/feedback",
        json={"thread_id": "t", "message_id": "t-0", "score": "up"},
    )
    assert resp.status_code == 502
    assert "timeout" in resp.json()["detail"].lower()


def test_feedback_uuidv4_thread_id_happy_path(monkeypatch, client):
    """Phase 7 D-10: UUIDv4 thread_id + integer turn_idx parses cleanly.

    Drift-prevention belt-and-braces alongside the FE Vitest+MSW round-trip
    (Plan 07-02 D-09). Catches any future regex tightening that would
    reject UUIDv4-shaped thread ids — the canonical 'abc-0' fixtures
    elsewhere in this file would miss that regression because the
    `_TURN_RE = re.compile(r"^(.+)-(\\d+)$")` regex anchors on the LAST
    `-<digits>` suffix and treats everything before as the thread_id (so
    UUIDv4 dashes are absorbed into the thread_id capture group).
    """
    from backend.api.routes import feedback as fb_mod

    captured: dict = {}
    fake = MagicMock()
    fake.create_score = lambda **kw: captured.update(kw)
    monkeypatch.setattr(fb_mod, "get_langfuse_client", lambda: fake)
    monkeypatch.setattr(
        fb_mod,
        "seed_trace_id",
        lambda tid, ti: f"trace-{tid}-{ti}",
    )

    thread_id = "a4b27c8e-d4f1-4ddd-aaaa-1234567890ab"
    turn_idx = 3
    message_id = f"{thread_id}-{turn_idx}"

    resp = client.post(
        "/api/feedback",
        json={
            "thread_id": thread_id,
            "message_id": message_id,
            "score": "up",
            "reason": "uuid-shape verification",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["delivered"] is True
    assert body["trace_id"] == f"trace-{thread_id}-{turn_idx}"
    assert captured["trace_id"] == f"trace-{thread_id}-{turn_idx}"
    assert captured["name"] == "user_feedback"
    assert captured["value"] == 1
    assert captured["comment"] == "uuid-shape verification"
