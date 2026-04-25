"""FastAPI application entry point (API-01..04).

Wires the LangGraph orchestrator behind a thin REST + SSE layer.
The compiled graph and its AsyncSqliteSaver checkpointer are created
once in the lifespan and stored on app.state — see Pattern 3 / D-15.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from backend.agent.graph import build_graph
from backend.api.routes.chat import router as chat_router
from backend.config import CHECKPOINT_PATH

logger = logging.getLogger(__name__)


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
        yield
    finally:
        await conn.close()


app = FastAPI(
    title="Express Dynamic Surcharge Orchestrator",
    version="0.3.0",
    lifespan=lifespan,
)
app.include_router(chat_router)


@app.get("/health")
async def health():
    """Readiness check for ops; returns 200 when graph is compiled."""
    return {
        "status": "ok",
        "graph_ready": getattr(app.state, "graph", None) is not None,
    }
