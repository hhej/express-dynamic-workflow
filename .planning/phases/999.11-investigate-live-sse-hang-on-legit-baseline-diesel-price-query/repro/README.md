# Phase 999.11 — Repro harness

Per D-03 / D-04 / D-09. NOT importable as a module; these are
operational scripts that talk to a fresh uvicorn subprocess over HTTP.

## Files

- `probe_legit_baseline.py` — single-run probe (D-03)
- `run_5x.sh` — 5-run orchestrator for the D-09 live verification bar
- `logs/` — per-run artifacts (SSE log + uvicorn stderr + summary.jsonl)

## Usage

### Single run

```bash
python .planning/phases/999.11-investigate-live-sse-hang-on-legit-baseline-diesel-price-query/repro/probe_legit_baseline.py \
  --run-id 001 \
  --sse-out  .planning/phases/999.11-investigate-live-sse-hang-on-legit-baseline-diesel-price-query/repro/logs/run-001-sse.log \
  --stderr-out .planning/phases/999.11-investigate-live-sse-hang-on-legit-baseline-diesel-price-query/repro/logs/run-001-uvicorn.stderr
```

### 5-run live bar (D-09)

```bash
bash .planning/phases/999.11-investigate-live-sse-hang-on-legit-baseline-diesel-price-query/repro/run_5x.sh
```

Exits 0 only if 5/5 runs produce `first_answer_ms < 30000`.

## D-06 disambiguator toggles

- `--skip-coldstart-refresh` — exports `EXPRESS_SKIP_COLDSTART_REFRESH=1` in
  the uvicorn subprocess env. Use to isolate the cold-start fuel refresh
  task from the hang. (Plan 999.11-02 hypothesis (c) — variant 1)
- `--warmup-first` — issues a `ping` POST before the real probe to warm
  the Gemini HTTP pool + Langfuse handler. Use to isolate cold-start LLM
  handshake from the hang. (Plan 999.11-02 hypothesis (c) — variant 2)

Forward to `run_5x.sh` the same way:

```bash
bash run_5x.sh --warmup-first
bash run_5x.sh --skip-coldstart-refresh
bash run_5x.sh --warmup-first --skip-coldstart-refresh
```

## What the probe captures (D-04)

Per run, EXACTLY two on-disk artifacts:

- `run-NNN-sse.log` — JSON array, every SSE `data:` line with
  `wall_clock` (ISO8601 UTC, millisecond precision, trailing `Z`) AND
  `elapsed_ms` (monotonic from request start).
- `run-NNN-uvicorn.stderr` — raw bytes of uvicorn stderr, including
  any logger.warning/exception from `_drain_events`, `_fresh_stream`,
  `_coldstart_fuel_refresh`, planner_node, fuel_agent_node, etc.

Stdout of the probe is a single-line JSON summary. `run_5x.sh` tees it
into `logs/summary.jsonl`.

## Why `bash run_5x.sh` (not `./run_5x.sh`)

The executor agent cannot `chmod +x` files inside its sandbox, so the
script is invoked via the `bash` interpreter explicitly. Functionally
identical to a chmod-ed direct invocation.

## Anti-patterns (DO NOT)

- Do NOT replace `subprocess.Popen` with the in-process ASGI test
  client — that mode is in-process and does not reproduce real
  cold-start Gemini handshakes (RESEARCH Pitfall 3).
- Do NOT pull Langfuse traces during the initial repro pass — D-04
  defers Langfuse inspection unless stderr+stream are insufficient.
- Do NOT reuse a single thread_id across the 5 runs — fresh `uuid4()`
  per probe avoids stale-state pollution (RESEARCH Pitfall 5).
