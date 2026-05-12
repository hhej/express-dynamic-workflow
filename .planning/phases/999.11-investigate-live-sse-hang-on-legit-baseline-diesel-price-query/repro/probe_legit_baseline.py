"""D-03 fresh-uvicorn + httpx probe for Phase 999.11 hang investigation.

Per D-03 / D-04: spawn a fresh ``uvicorn backend.api.main:app`` subprocess,
wait for ``/health`` readiness, then drain the SSE stream from
``POST /api/chat`` with both wall-clock ISO8601-Z and elapsed-ms timestamps
on every event. Captures EXACTLY two artifacts per run:

    1. ``--sse-out``    : JSON array of all SSE ``data:`` envelopes.
    2. ``--stderr-out`` : raw bytes of uvicorn stderr (lifespan logs,
                          ``_drain_events`` warnings, swallowed exceptions).

Per D-06 the probe exposes two disambiguator toggles for hypothesis (c):

    --skip-coldstart-refresh : set ``EXPRESS_SKIP_COLDSTART_REFRESH=1`` in
                               the subprocess env so the lifespan does NOT
                               schedule the background fuel CSV refresh.
    --warmup-first           : issue a short ``ping`` POST before the real
                               probe to warm the Gemini HTTP pool + the
                               Langfuse callback handler.

The probe is intentionally OUT-OF-PROCESS — it does NOT import any
``backend.*`` module. The hang is a live-server symptom; reproducing it
via the in-process ASGI test client would short-circuit the real
cold-start ASGI + Gemini handshake (RESEARCH Pitfall 3).

The 180s client timeout is deliberately MUCH larger than the 60s observed
live hang so the probe captures the full surface area of the failure
mode without prematurely closing the stream.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Resolve the repo root four levels up from this file:
#   repro -> 999.11-... -> phases -> .planning -> <repo>
REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_MESSAGE = "What's the current diesel price in Bangkok?"
DEFAULT_PORT = "8765"
READINESS_TIMEOUT_S = 30.0
READINESS_POLL_INTERVAL_S = 0.5
CLIENT_TIMEOUT_S = 180.0
SHUTDOWN_TIMEOUT_S = 10.0
WARMUP_TIMEOUT_S = 60.0


def _wall_clock_z() -> str:
    """Return current wall-clock as ISO8601 UTC with trailing ``Z``.

    Returns:
        ISO8601 timestamp with millisecond precision and ``Z`` suffix,
        e.g. ``"2026-05-11T14:42:01.123Z"``.
    """
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _build_env(skip_coldstart_refresh: bool) -> dict[str, str]:
    """Construct env vars for the uvicorn subprocess.

    Args:
        skip_coldstart_refresh: When True, set
            ``EXPRESS_SKIP_COLDSTART_REFRESH=1`` so the lifespan skips the
            background fuel CSV refresh (D-06 hypothesis (c) variant 1).

    Returns:
        Dict suitable for ``subprocess.Popen(env=...)``. Inherits the
        current process env and always sets ``PYTHONUNBUFFERED=1`` so
        uvicorn stderr flushes line-by-line — essential for D-04 stderr
        capture timing.
    """
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    if skip_coldstart_refresh:
        env["EXPRESS_SKIP_COLDSTART_REFRESH"] = "1"
    return env


async def _await_readiness(port: str) -> float:
    """Poll ``/health`` until uvicorn reports ``graph_ready=True``.

    Args:
        port: TCP port the uvicorn subprocess is listening on.

    Returns:
        Monotonic seconds elapsed from poll-start to readiness.

    Raises:
        RuntimeError: If ``READINESS_TIMEOUT_S`` elapses without a
            healthy response.
    """
    poll_start = time.monotonic()
    deadline = poll_start + READINESS_TIMEOUT_S
    url = f"http://127.0.0.1:{port}/health"
    async with httpx.AsyncClient(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                r = await client.get(url)
                if r.status_code == 200 and r.json().get("graph_ready") is True:
                    return time.monotonic() - poll_start
            except Exception:
                pass
            await asyncio.sleep(READINESS_POLL_INTERVAL_S)
    raise RuntimeError(
        f"uvicorn did not become healthy in {READINESS_TIMEOUT_S}s"
    )


async def _drain_sse(
    port: str, message: str, thread_id: str
) -> tuple[list[dict], int, int | None, str]:
    """Issue the legit-baseline POST and drain the SSE stream.

    Records every ``data:`` envelope with both wall-clock and
    monotonic-elapsed-ms timestamps so the hang's timing surface is
    reconstructible after the fact (D-04 contract).

    Args:
        port: TCP port the uvicorn subprocess is listening on.
        message: User message body to send to ``POST /api/chat``.
        thread_id: Opaque thread identifier (fresh ``uuid4`` per run
            per RESEARCH Pitfall 5).

    Returns:
        Tuple of:
            - ``events``: list of envelope dicts (wall_clock, elapsed_ms,
              type, payload).
            - ``stream_close_ms``: monotonic ms from request-start to
              stream close (clean or timed-out).
            - ``first_answer_ms``: monotonic ms to the first ``answer``
              SSE event, or ``None`` if none was observed.
            - ``error_str``: ``repr(exc)`` if an exception interrupted
              the stream drain, else empty string. NOT raised — the
              hang itself is the diagnostic.
    """
    events: list[dict] = []
    error_str = ""
    request_start = time.monotonic()
    url = f"http://127.0.0.1:{port}/api/chat"
    payload = {"message": message, "thread_id": thread_id}
    try:
        async with httpx.AsyncClient(timeout=CLIENT_TIMEOUT_S) as client:
            async with client.stream("POST", url, json=payload) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    elapsed_ms = int((time.monotonic() - request_start) * 1000)
                    try:
                        envelope = json.loads(line[len("data: "):])
                    except json.JSONDecodeError as exc:
                        error_str = f"json_decode: {exc!r}"
                        break
                    events.append(
                        {
                            "wall_clock": _wall_clock_z(),
                            "elapsed_ms": elapsed_ms,
                            "type": envelope.get("type"),
                            "payload": envelope.get("payload"),
                        }
                    )
    except Exception as exc:
        # The hang itself is the diagnostic — do NOT raise.
        error_str = repr(exc)

    stream_close_ms = int((time.monotonic() - request_start) * 1000)
    first_answer_ms = next(
        (e["elapsed_ms"] for e in events if e["type"] == "answer"), None
    )
    return events, stream_close_ms, first_answer_ms, error_str


async def _do_warmup(port: str) -> dict:
    """Issue a short ``ping`` POST to warm the Gemini + Langfuse pools.

    Uses a SHORT 60s timeout because guard_input's domain allow-list
    refusal path completes in sub-second; a hung warmup means the
    underlying repro environment is broken and the test is invalid.

    Args:
        port: TCP port the uvicorn subprocess is listening on.

    Returns:
        Summary dict with ``events``, ``first_answer_ms``, ``done_ms``,
        and ``elapsed_ms`` keys. Best-effort — exceptions are captured
        in an ``error`` key rather than raised.
    """
    request_start = time.monotonic()
    events: list[dict] = []
    error_str = ""
    thread_id = "warmup-" + uuid.uuid4().hex
    url = f"http://127.0.0.1:{port}/api/chat"
    payload = {"message": "ping", "thread_id": thread_id}
    try:
        async with httpx.AsyncClient(timeout=WARMUP_TIMEOUT_S) as client:
            async with client.stream("POST", url, json=payload) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    elapsed_ms = int((time.monotonic() - request_start) * 1000)
                    try:
                        envelope = json.loads(line[len("data: "):])
                    except json.JSONDecodeError:
                        continue
                    events.append(
                        {
                            "elapsed_ms": elapsed_ms,
                            "type": envelope.get("type"),
                        }
                    )
    except Exception as exc:
        error_str = repr(exc)

    first_answer_ms = next(
        (e["elapsed_ms"] for e in events if e["type"] == "answer"), None
    )
    done_ms = next(
        (e["elapsed_ms"] for e in events if e["type"] == "done"), None
    )
    return {
        "events": len(events),
        "first_answer_ms": first_answer_ms,
        "done_ms": done_ms,
        "elapsed_ms": int((time.monotonic() - request_start) * 1000),
        "error": error_str,
    }


async def _probe(args: argparse.Namespace, env: dict[str, str]) -> dict:
    """Orchestrate a single fresh-uvicorn probe run.

    Spawns uvicorn, waits for readiness, optionally issues a warmup POST,
    drains the real legit-baseline SSE stream, persists the event log
    to ``args.sse_out``, then SIGINT-shutsdown uvicorn while keeping the
    stderr file open the whole time (D-04 capture contract).

    Args:
        args: Parsed CLI namespace from ``main``.
        env: Subprocess env (already merged by ``_build_env``).

    Returns:
        Single-line-JSON-friendly summary dict — see ``main`` for the
        downstream consumer (run_5x.sh tees it to summary.jsonl).
    """
    # Fail fast if REPO_ROOT detection went wrong — the parents[4] math
    # is fragile if the file is ever moved.
    assert (REPO_ROOT / "backend" / "api" / "main.py").exists(), REPO_ROOT

    stderr_path = Path(args.stderr_out)
    sse_path = Path(args.sse_out)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    sse_path.parent.mkdir(parents=True, exist_ok=True)

    stderr_f = open(stderr_path, "wb")
    proc = subprocess.Popen(
        [
            "uvicorn",
            "backend.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            args.port,
            "--log-level",
            "info",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stderr=stderr_f,
        stdout=subprocess.DEVNULL,
    )

    summary: dict = {
        "run_id": args.run_id,
        "message": args.message,
        "skip_coldstart_refresh": bool(args.skip_coldstart_refresh),
        "warmup_first": bool(args.warmup_first),
    }
    try:
        readiness_s = await _await_readiness(args.port)
        summary["readiness_s"] = round(readiness_s, 3)

        warmup_summary: dict | None = None
        if args.warmup_first:
            warmup_summary = await _do_warmup(args.port)
        summary["warmup"] = warmup_summary

        thread_id = "probe-" + uuid.uuid4().hex
        summary["thread_id"] = thread_id

        events, stream_close_ms, first_answer_ms, error_str = await _drain_sse(
            args.port, args.message, thread_id
        )

        sse_path.write_text(
            json.dumps(events, indent=2, ensure_ascii=False)
        )

        done_ms = next(
            (e["elapsed_ms"] for e in events if e["type"] == "done"), None
        )
        total_elapsed_ms = events[-1]["elapsed_ms"] if events else None
        types = [e["type"] for e in events]

        summary["event_count"] = len(events)
        summary["types"] = types
        summary["first_answer_ms"] = first_answer_ms
        summary["done_ms"] = done_ms
        summary["stream_close_ms"] = stream_close_ms
        summary["total_elapsed_ms"] = total_elapsed_ms
        summary["error_str"] = error_str
        if first_answer_ms is not None and first_answer_ms < 30_000:
            summary["verdict"] = "PASS_UNDER_30S"
        else:
            summary["verdict"] = "FAIL"
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=SHUTDOWN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
        stderr_f.close()

    return summary


def main() -> None:
    """CLI entry point — see module docstring for the contract."""
    parser = argparse.ArgumentParser(
        description=(
            "D-03 fresh-uvicorn + httpx probe for the Phase 999.11 "
            "legit-baseline hang."
        )
    )
    parser.add_argument("--run-id", required=True, help="Run identifier (e.g. 001)")
    parser.add_argument(
        "--sse-out",
        required=True,
        help="Path to write the JSON SSE event log (D-04 artifact 1)",
    )
    parser.add_argument(
        "--stderr-out",
        required=True,
        help="Path to write raw uvicorn stderr (D-04 artifact 2)",
    )
    parser.add_argument(
        "--message",
        default=DEFAULT_MESSAGE,
        help=f"User message body (default: {DEFAULT_MESSAGE!r})",
    )
    parser.add_argument(
        "--skip-coldstart-refresh",
        action="store_true",
        help=(
            "Set EXPRESS_SKIP_COLDSTART_REFRESH=1 in subprocess env — "
            "D-06 isolator for hypothesis (c) variant 1"
        ),
    )
    parser.add_argument(
        "--warmup-first",
        action="store_true",
        help=(
            "Issue 'ping' POST before real probe — D-06 isolator for "
            "hypothesis (c) variant 2"
        ),
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        help=f"uvicorn TCP port (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    env = _build_env(skip_coldstart_refresh=args.skip_coldstart_refresh)
    summary = asyncio.run(_probe(args, env))
    sys.stdout.write(json.dumps(summary) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
