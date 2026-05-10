"""Shared pytest fixtures for Phase 2 tests.

Consumed by test_fetch_fuel_price.py, test_calculate_route.py,
test_lookup_rate.py, test_calculate_surcharge_tool.py,
test_fuel_agent.py, test_route_agent.py.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
import pytest_asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_agent_state() -> dict:
    """A minimal valid AgentState dict for node tests (ORCH-02, ORCH-03)."""
    return {
        "messages": [],
        "fuel_data": None,
        "route_data": None,
        "shipping_type": "bounce",
        "weight_kg": 10.0,
        "surcharge_result": None,
        "reasoning_trace": [],
        "next_step": "",
    }


@pytest.fixture
def eppo_html_fixture() -> str:
    """Captured EPPO HTML sample (TOOL-01 tests)."""
    return (_FIXTURES_DIR / "eppo_sample.html").read_text(encoding="utf-8")


@pytest.fixture
def gmaps_directions_fixture() -> list[dict[str, Any]]:
    """Captured googlemaps.directions() response (TOOL-02 tests).

    Ratio duration_in_traffic/duration = 2400/1800 = 1.333 -> severity 3.
    """
    return json.loads((_FIXTURES_DIR / "gmaps_directions.json").read_text())


@pytest.fixture
def gmaps_geocode_bangkok_fixture() -> list[dict[str, Any]]:
    """Captured googlemaps.reverse_geocode() for Bangkok (central-1)."""
    return json.loads((_FIXTURES_DIR / "gmaps_geocode_bangkok.json").read_text())


@pytest.fixture
def gmaps_geocode_ayutthaya_fixture() -> list[dict[str, Any]]:
    """Captured googlemaps.reverse_geocode() for Ayutthaya (central-2).

    Uses 'Ayutthaya Province' form to exercise Pitfall 6 normalisation.
    """
    return json.loads((_FIXTURES_DIR / "gmaps_geocode_ayutthaya.json").read_text())


@pytest.fixture
def gmaps_geocode_lopburi_fixture() -> list[dict[str, Any]]:
    """Captured googlemaps.reverse_geocode() for Lop Buri (central-3)."""
    return json.loads((_FIXTURES_DIR / "gmaps_geocode_lopburi.json").read_text())


@pytest.fixture
def seeded_sqlite_path(tmp_path: Path) -> Path:
    """A fresh copy of data/express.db for TOOL-03 tests.

    Copies the real seeded DB into a tmp path so tests can open/query it
    without risk of modification. Avoids in-memory re-seeding; reuses the
    Phase 1 seeded rate_table exactly as shipped.
    """
    repo_root = Path(__file__).resolve().parents[2]
    source = repo_root / "data" / "express.db"
    target = tmp_path / "express_test.db"
    target.write_bytes(source.read_bytes())
    return target


@pytest_asyncio.fixture
async def in_memory_checkpointer():
    """An AsyncSqliteSaver backed by an in-memory SQLite DB.

    Tables are created via `setup()` before yield; the connection is
    closed in teardown. Used by graph integration tests (D-25) and
    API tests (D-26) to avoid checkpoint pollution across tests.

    Implementation note: aiosqlite.connect returns an awaitable Connection
    that becomes "alive" only when entered as an async context manager (or
    awaited). AsyncSqliteSaver.setup() relies on conn.is_alive(), so we
    must use `async with` here -- raw `await aiosqlite.connect(...)` does
    NOT activate the connection thread.
    """
    async with aiosqlite.connect(":memory:") as conn:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        yield saver


# ----- Phase 5 fixtures -----


@pytest.fixture
def mock_langfuse(monkeypatch):
    """Phase 5: forces _enabled() to False so observability helpers
    return None / no-op. Tests that want to assert calls were made
    should NOT use this fixture; they should monkeypatch
    get_langfuse_client directly to return a Mock.
    """
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    # Reload module to pick up env changes if it was already imported.
    import importlib
    import backend.agent.observability as _obs
    importlib.reload(_obs)
    yield _obs


@pytest.fixture
def mock_tavily_client(monkeypatch):
    """Phase 5: stub tavily.TavilyClient.search() with a fixed payload.

    Plans 05-04 (search agent) and 05-06 (e2e) will replace .search
    return_value per-test as needed.
    """
    from unittest.mock import MagicMock
    client = MagicMock()
    client.search.return_value = {
        "query": "diesel news",
        "answer": "Diesel prices in Thailand are stable this week.",
        "results": [
            {
                "title": "EPPO weekly diesel report",
                "url": "https://example.com/diesel",
                "content": "Diesel B7 retail price held at 30 THB/L for the third week.",
                "published_date": "2026-05-01",
            },
        ],
    }
    # Patch the constructor so any code that instantiates
    # tavily.TavilyClient(...) gets this mock back.
    from tavily import TavilyClient  # noqa: F401  type: ignore[import-untyped]
    monkeypatch.setattr(
        "tavily.TavilyClient",
        lambda *a, **kw: client,
        raising=True,
    )
    return client


@pytest.fixture
def mock_pricing_low():
    """Phase 5: surcharge_result with total <= HITL_TOTAL_THB_THRESHOLD.
    Used by test_hitl_gate.py to assert the bypass path.
    """
    return {
        "surcharge_pct": 0.05,
        "surcharge_amount": 10.0,
        "total": 210.0,  # well below the 500 default threshold
        "capped": False,
    }


@pytest.fixture
def mock_pricing_high():
    """Phase 5: surcharge_result with total > HITL_TOTAL_THB_THRESHOLD.
    Used by test_hitl_gate.py to assert the interrupt() path.
    """
    return {
        "surcharge_pct": 0.10,
        "surcharge_amount": 65.0,
        "total": 715.0,  # above the 500 default threshold
        "capped": False,
    }


# ----- Phase 999.9 fixtures -----


@pytest.fixture
def mock_hubs_json(monkeypatch):
    """Test fixture: monkeypatch _HUB_INDEX to a minimal 3-hub set
    covering all three zones for downstream agent tests.

    Lets Wave 2 tests (planner, pricing_agent, route_agent) isolate from
    the prod hubs.json without re-loading from disk.
    """
    from backend.agent.tools import hubs as hubs_module

    test_hubs = {
        "hq-lat-krabang": {
            "name": "Express HQ — Lat Krabang Industrial Estate, Bangkok",
            "address": "Lat Krabang Industrial Estate, Bangkok",
            "zone": "central-1",
        },
        "branch-bang-na": {
            "name": "Express Branch — Bang Na, Bangkok",
            "address": "Bang Na, Bangkok",
            "zone": "central-1",
        },
        "branch-ayutthaya": {
            "name": "Express Branch — Phra Nakhon Si Ayutthaya",
            "address": "Phra Nakhon Si Ayutthaya, Ayutthaya",
            "zone": "central-2",
        },
    }
    monkeypatch.setattr(hubs_module, "_HUB_INDEX", test_hubs)
    return test_hubs
