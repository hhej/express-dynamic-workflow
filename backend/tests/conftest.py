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
