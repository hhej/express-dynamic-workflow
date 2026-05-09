"""FastAPI application entry point (API-01..04).

Wires the LangGraph orchestrator behind a thin REST + SSE layer.
The compiled graph and its AsyncSqliteSaver checkpointer are created
once in the lifespan and stored on app.state — see Pattern 3 / D-15.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.agent.graph import build_graph
from backend.api.routes.chat import router as chat_router
from backend.api.routes.conversations import router as conversations_router
from backend.api.routes.feedback import router as feedback_router
from backend.api.routes.fuel_prices import router as fuel_prices_router
from backend.config import CHECKPOINT_PATH, EXPRESS_SKIP_COLDSTART_REFRESH

# Quick 260509-eum: make data/scripts importable as a module. The script
# lives outside the backend package, so we resolve REPO_ROOT and append
# it to sys.path once at import time. This is a deliberate cross-package
# reuse -- the alternative (duplicating refresh_csv into backend/) is
# ruled out by the quick-task constraint "DO NOT duplicate scrape
# logic" and CONTEXT D-03 reuse contract.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Import after sys.path manipulation. Aliased so the symbol is easy to
# monkeypatch in tests (`monkeypatch.setattr(_main, "refresh_fuel_csv", stub)`).
from data.scripts.fetch_fuel_prices import refresh_csv as refresh_fuel_csv  # noqa: E402

logger = logging.getLogger(__name__)


async def _coldstart_fuel_refresh() -> None:
    """Run the blocking refresh_fuel_csv() in a worker thread.

    D-02: must not block the event loop -- ``asyncio.to_thread`` shunts
    the synchronous ``requests.get`` call off the loop. D-03: any
    exception is logged and swallowed; the existing CSV is left
    untouched and the dashboard renders last-known data.
    """
    try:
        refreshed = await asyncio.to_thread(refresh_fuel_csv)
        if refreshed:
            logger.info("Cold-start fuel CSV refresh: completed")
        # When refreshed is False, refresh_fuel_csv has already logged
        # the reason (fresh OR scrape failed) at the appropriate level;
        # no extra log here.
    except Exception as exc:
        # refresh_fuel_csv already swallows internal errors; this is the
        # outer net for asyncio.to_thread / scheduling failures.
        logger.warning(
            "Cold-start fuel CSV refresh: scheduling error: %s",
            exc,
            exc_info=True,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open AsyncSqliteSaver, compile the graph, expose on app.state."""
    Path(CHECKPOINT_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(CHECKPOINT_PATH)
    try:
        checkpointer = AsyncSqliteSaver(conn)
        await checkpointer.setup()  # Pitfall 9: idempotent table creation
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        logger.info("Graph compiled with AsyncSqliteSaver(%s)", CHECKPOINT_PATH)

        # Quick 260509-eum: schedule fuel CSV refresh BEFORE yield,
        # but DO NOT await -- API begins accepting traffic immediately
        # (D-02). Hold a reference on app.state so GC cannot collect
        # the task mid-flight (asyncio docs: "Save a reference to the
        # result of [create_task], to avoid a task disappearing
        # mid-execution.").
        if not EXPRESS_SKIP_COLDSTART_REFRESH:
            app.state.coldstart_refresh_task = asyncio.create_task(
                _coldstart_fuel_refresh()
            )
            logger.info("Cold-start fuel CSV refresh: scheduled in background")
        else:
            app.state.coldstart_refresh_task = None
            logger.info(
                "Cold-start fuel CSV refresh: skipped "
                "(EXPRESS_SKIP_COLDSTART_REFRESH set)"
            )

        yield
    finally:
        await conn.close()


app = FastAPI(
    title="Express Dynamic Surcharge Orchestrator",
    version="0.3.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(fuel_prices_router)
app.include_router(feedback_router)


@app.get("/health")
async def health():
    """Readiness check for ops; returns 200 when graph is compiled."""
    return {
        "status": "ok",
        "graph_ready": getattr(app.state, "graph", None) is not None,
    }
