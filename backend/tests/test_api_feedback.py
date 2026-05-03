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
