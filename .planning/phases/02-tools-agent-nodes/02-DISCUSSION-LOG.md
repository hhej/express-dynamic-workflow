# Phase 2: Tools & Agent Nodes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-18
**Phase:** 02-tools-agent-nodes
**Areas discussed:** Fuel fetch fallback chain, Route tool & zone mapping, Agent node reasoning style, lookup_rate & testing strategy

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Fuel fetch fallback chain | How to structure API → scrape → cached CSV → last-known when EPPO format is undocumented | ✓ |
| Route tool & zone mapping | Google Maps integration — zone derivation, traffic 1-5 derivation | ✓ |
| Agent node reasoning style | Fuel & Route Agent nodes — LLM-driven vs deterministic wrappers | ✓ |
| lookup_rate & testing strategy | Boundary handling, error semantics, test mocking approach | ✓ |

**User's choice:** All four areas selected.

---

## Fuel fetch fallback chain

### Q1: Fallback chain structure given no public EPPO API

| Option | Description | Selected |
|--------|-------------|----------|
| Scrape → CSV → hardcoded | 3 levels: live EPPO scrape → seed CSV → BASELINE_DIESEL_PRICE constant | ✓ |
| Scrape → PTT scrape → CSV → hardcoded | 4 levels with PTT as second live source | |
| Scrape → CSV (no hardcoded fallback) | 2 levels only; raise if CSV missing | |

**User's choice:** Scrape → CSV → hardcoded.
**Notes:** Matches reality that EPPO has no stable API; avoids doubling scraping code for PTT.

### Q2: HTTP/parsing library

| Option | Description | Selected |
|--------|-------------|----------|
| httpx + BeautifulSoup (Recommended) | Async-native, standard HTML parser | ✓ |
| requests + BeautifulSoup | Sync only; needs asyncio.to_thread wrapper | |
| Playwright | Overkill unless EPPO is SPA | |

**User's choice:** httpx + BeautifulSoup.

### Q3: How to signal which fallback level was hit

| Option | Description | Selected |
|--------|-------------|----------|
| FuelData.source enum (Recommended) | Expand existing enum: eppo_live, eppo_cached_csv, hardcoded_baseline | ✓ |
| Add fallback_level field | Keep source for provenance; add int for level | |
| Log via reasoning_trace only | Keep FuelData clean; prose-only signal | |

**User's choice:** Expand FuelData.source enum.

### Q4: Live-fetch retry policy before falling back

| Option | Description | Selected |
|--------|-------------|----------|
| 2 retries, 1s then 2s (Recommended) | Exponential backoff inside the tool | ✓ |
| No retries — fall straight to CSV | Defer retry logic to Phase 3 agentic wrapper | |
| 1 retry, no backoff | Minimal transient-blip handling | |

**User's choice:** 2 retries with 1s/2s exponential backoff.

---

## Route tool & zone mapping

### Q1: How to derive zone (central-1/-2/-3)

| Option | Description | Selected |
|--------|-------------|----------|
| Destination geocode → province match (Recommended) | Reverse-geocode destination, match province → zone_definitions.json | ✓ |
| Parse destination string directly | Extract province name from raw input string | |
| Use Gemini to classify | LLM classification; non-deterministic | |

**User's choice:** Destination geocode → province match.

### Q2: Traffic severity (1-5) derivation

| Option | Description | Selected |
|--------|-------------|----------|
| Ratio-based thresholds (Recommended) | duration_in_traffic / duration bucketed into 5 levels | ✓ |
| Absolute delay thresholds | Based on extra minutes; penalizes long routes | |
| Ask Gemini to rate it | Agentic but non-deterministic | |

**User's choice:** Ratio-based thresholds.

### Q3: Route cache location

| Option | Description | Selected |
|--------|-------------|----------|
| functools.lru_cache with TTL wrapper (Recommended) | In-process dict, resets on restart | ✓ |
| Store in AgentState route_data only | Per-conversation, no cross-thread cache | |
| SQLite-backed cache | Persistent, more complexity | |

**User's choice:** In-process TTL wrapper.

### Q4: Dev/test strategy for Google Maps

| Option | Description | Selected |
|--------|-------------|----------|
| Live during dev, mocks in tests (Recommended) | Real API in dev; pre-recorded JSON in tests | ✓ |
| Fixtures always; live only on demo | Zero dev spend; flip to live at demo | |
| Live everywhere | Trust the $200 credit; simplest code | |

**User's choice:** Live during dev, mocks in tests.

---

## Agent node reasoning style

### Q1: How much LLM reasoning inside Fuel/Route nodes

| Option | Description | Selected |
|--------|-------------|----------|
| LLM-wrapped tool calls (Recommended) | Full agentic pattern: LLM decides tool call, summarises result | ✓ |
| Deterministic wrapper, LLM for narration only | Tool called directly; LLM explains result | |
| Pure deterministic | No LLM in these nodes; Planner/Pricing handle reasoning | |

**User's choice:** LLM-wrapped tool calls.

### Q2: Prompt input strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Node receives pre-extracted state (Recommended) | Planner extracts fields; nodes read state, not messages | ✓ |
| Node re-parses last user message | Each node does its own parsing | |
| Hybrid — state first, fallback to parse | Resilient but more code paths | |

**User's choice:** Pre-extracted state.

### Q3: Gemini structured output fallback

| Option | Description | Selected |
|--------|-------------|----------|
| Retry once, then deterministic path (Recommended) | Stricter reprompt; fall to canned trace on second failure | ✓ |
| Raise and let Phase 3 retry loop handle | Simpler node, untested against malformed output | |
| Use LangChain with_structured_output helper | Delegate parsing | |

**User's choice:** Retry once, then deterministic.

### Q4: reasoning_trace entry schema

| Option | Description | Selected |
|--------|-------------|----------|
| Rich structured records (Recommended) | step, agent, tool, tool_input, tool_output, reasoning, timestamp, status | ✓ |
| Minimal: step + text | Prose-heavy; harder Langfuse mapping | |
| LangChain AgentAction style | Familiar tuple shape; still needs translation | |

**User's choice:** Rich structured records.

---

## lookup_rate & testing strategy

### Q1: Weight tier boundary semantics

| Option | Description | Selected |
|--------|-------------|----------|
| Half-open: [min, max) (Recommended) | 5kg → '5-10' tier; top tier has max=NULL | ✓ |
| Inclusive both ends: [min, max] | Requires tiebreaker | |
| Tier width as string label only | Label parsing feels brittle | |

**User's choice:** Half-open [min, max).

### Q2: Error semantics on lookup miss

| Option | Description | Selected |
|--------|-------------|----------|
| Raise ValueError with context (Recommended) | Consistent with calculate_surcharge D-11 | ✓ |
| Return RateResult with base_rate=0 + warning | Never breaks graph; risky semantics | |
| Return None | Simple but breaks Pydantic contract | |

**User's choice:** Raise ValueError.

### Q3: Test strategy for external APIs

| Option | Description | Selected |
|--------|-------------|----------|
| responses library for HTTP mocks (Recommended) | Record real EPPO HTML + Maps JSON, replay offline | ✓ |
| VCR.py cassette recording | Cassette hygiene overhead | |
| Hand-crafted fixtures | No extra lib; loses realism | |

**User's choice:** responses library.

### Q4: Agent node LLM mocking

| Option | Description | Selected |
|--------|-------------|----------|
| Mock LLM at langchain level (Recommended) | FakeListChatModel replays scripted responses | ✓ |
| Mock only the tool, let LLM run live | Flaky tests, quota burn | |
| Skip node-level tests | Fails success criterion #4 | |

**User's choice:** Mock LLM at langchain level.

---

## Claude's Discretion

Areas where user deferred to Claude (per CONTEXT.md):
- Exact module layout/filenames for new tools
- Config key names/defaults for traffic-ratio thresholds
- `responses` adapter configuration detail (requests vs httpx MockTransport)
- TTL wrapper internal structure
- Gemini system-prompt wording for Fuel/Route agents

## Deferred Ideas

None raised during discussion — scope stayed within Phase 2.
