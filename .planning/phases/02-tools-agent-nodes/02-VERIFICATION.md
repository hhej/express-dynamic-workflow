---
phase: 02-tools-agent-nodes
verified: 2026-04-18T08:07:29Z
status: passed
score: 4/4 success criteria verified; 6/6 requirement IDs satisfied
re_verification:
  previous_status: null
  note: "Initial verification (no prior VERIFICATION.md)"
---

# Phase 02: Tools & Agent Nodes Verification Report

**Phase Goal:** Each tool (fuel fetch, route calc, rate lookup, surcharge calc) works independently with tests, and is wrapped in a LangGraph-compatible agent node.

**Verified:** 2026-04-18T08:07:29Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | fetch_fuel_price tool returns current diesel price via multi-level fallback chain (API -> cached CSV -> last-known) and returns a structured Pydantic response | VERIFIED | `backend/agent/tools/fetch_fuel_price.py` implements 3-level chain (Level 1 stubbed w/ NotImplementedError per Open Question 2, Level 2 CSV, Level 3 baseline). 6 tests pass in `test_fetch_fuel_price.py` covering all 3 paths + retry timing [1, 2]. Smoke test: returned `FuelData(source='eppo_cached_csv', price=31.62, delta_pct=0.0561)` for real CSV. |
| 2 | calculate_route tool returns distance, duration, traffic severity, and zone for a given origin/destination pair (tested with mocked Google Maps responses) | VERIFIED | `backend/agent/tools/calculate_route.py` implements Directions + Geocoding + TTLCache. 12 test cases pass in `test_calculate_route.py` (directions parsing, parametrised bucketing [1.05,1.2,1.4,1.7,2.0], zone derivation for central-1/2/3, cache hit + expiry, two ValueError paths). Mocks via `pytest-mock`. |
| 3 | lookup_rate tool queries SQLite and returns the correct rate for a given shipping_type + zone + weight combination | VERIFIED | `backend/agent/tools/lookup_rate.py` implements half-open `WHERE weight_min_kg <= ? AND ? < weight_max_kg` SQL with sentinel 999 for top tier (C-02). 8 tests pass covering happy path, 5-kg boundary (D-13), error paths (unknown ship type/zone, sentinel weight, non-positive weight, top-tier format). Smoke tests returned `base_rate=85.0, tier='5-10kg'` for bounce/central-1/7.5kg and `base_rate=698.0, tier='50+kg'` for retail_fast/central-3/55kg. |
| 4 | Fuel Agent and Route Agent nodes can be invoked individually with a sample AgentState and produce correct state updates | VERIFIED | `backend/agent/nodes/fuel_agent.py` (ORCH-02) and `backend/agent/nodes/route_agent.py` (ORCH-03) implemented with Gemini narration + D-11 deterministic fallback + D-12 trace schema. 9 tests pass (4 fuel + 5 route). Live smoke test: `fuel_agent_node(sample_state)` returned `{fuel_data, reasoning_trace}` with trace entry containing all 8 D-12 keys (step/agent/tool/tool_input/tool_output/reasoning/timestamp/status) and fell back to deterministic narration when Gemini auth was unavailable (status still "ok"). |

**Score:** 4/4 success criteria verified

### Required Artifacts (from must_haves across 5 plans)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `requirements.txt` | Phase 2 deps (langgraph, langchain-google-genai, googlemaps, httpx, pytest-httpx, pytest-mock, langchain-core) | VERIFIED | All 7 pins present (lines 9-16). `.venv` confirmed importable for all. |
| `backend/config.py` | GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS, TRAFFIC_RATIO_BUCKETS, GOOGLE_MAPS_API_KEY, GOOGLE_API_KEY | VERIFIED | All six constants present (lines 30-50). Defaults match plan (gemini-2.0-flash, 10s, 900s, [1.1,1.3,1.5,1.8]). |
| `backend/agent/state.py` | `Annotated[List[dict], operator.add]` reducer on `reasoning_trace` (Pitfall 1) | VERIFIED | Line 35 exact match; `import operator` at line 4, `from typing_extensions import Annotated` at line 7. |
| `backend/agent/tools/models.py` | FuelData source docstring lists eppo_live \| eppo_cached_csv \| hardcoded_baseline | VERIFIED | Class docstring line 62 and Field description lines 73-75 mention all three. |
| `pyproject.toml` | `[tool.pytest.ini_options]` with testpaths | VERIFIED | File exists, 8 lines, configures testpaths="backend/tests". |
| `.env.example` | Phase 2 env vars documented | VERIFIED | Lines 26-30 add GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS, TRAFFIC_RATIO_BUCKETS. |
| `backend/tests/conftest.py` | 7 reusable fixtures | VERIFIED | `sample_agent_state`, `eppo_html_fixture`, `gmaps_directions_fixture`, `gmaps_geocode_bangkok_fixture`, `gmaps_geocode_ayutthaya_fixture`, `gmaps_geocode_lopburi_fixture`, `seeded_sqlite_path` all defined. |
| `backend/tests/fixtures/*` | 5 fixture files (HTML + 4 JSON) | VERIFIED | eppo_sample.html, gmaps_directions.json, gmaps_geocode_{bangkok,ayutthaya,lopburi}.json all exist; Ayutthaya JSON contains "Ayutthaya Province" suffix for Pitfall 6. |
| `backend/agent/tools/fetch_fuel_price.py` (TOOL-01) | 3-level fallback chain, `fetch_fuel_price()`, stubbed `_scrape_eppo_live()`, `_read_cached_csv()`, `_build_fuel_data()` | VERIFIED | 115 lines, all functions present, NotImplementedError documented for Level 1. |
| `backend/agent/tools/_cache.py` | TTLCache class with get/set/clear and Lock | VERIFIED | 52 lines, thread-safe dataclass with all three methods. |
| `backend/agent/tools/calculate_route.py` (TOOL-02) | `calculate_route`, `_bucket_traffic`, `_normalize_province`, `_load_zone_index`, `_zone_for_destination`, `_client`, TTLCache integration, departure_time+traffic_model | VERIFIED | 160 lines, all helpers present, `googlemaps.Client(key=...)` lazy init, zone JSON loaded at import time. |
| `backend/agent/tools/lookup_rate.py` (TOOL-03) | `lookup_rate()` with half-open SQL (C-02) + sentinel 999 | VERIFIED | 76 lines, SQL uses `? < weight_max_kg`, sqlite3.connect context manager, ValueError on miss with full context. |
| `backend/agent/tools/calculate_surcharge_tool.py` (TOOL-04) | `@tool("calculate_surcharge", args_schema=SurchargeInput)` | VERIFIED | 44 lines, decorator present, delegates to Phase 1 pure function. |
| `backend/agent/llm.py` | `get_chat_model()` factory returning ChatGoogleGenerativeAI | VERIFIED | 30 lines, temperature=0, max_retries=0 as planned. |
| `backend/agent/prompts/fuel_agent.py` | SYSTEM_PROMPT; does NOT advertise search_fuel_news | VERIFIED | Present, search_fuel_news not mentioned (Open Question 3 honoured). |
| `backend/agent/prompts/route_agent.py` | SYSTEM_PROMPT for RouteReasoning | VERIFIED | Present, describes RouteReasoning schema. |
| `backend/agent/nodes/fuel_agent.py` (ORCH-02) | `fuel_agent_node(state)` wrapping fetch_fuel_price + LLM narration + D-11 fallback + D-12 trace | VERIFIED | 130 lines, try/except catches any exception to deterministic narration, D-12 8-key schema. |
| `backend/agent/nodes/route_agent.py` (ORCH-03) | `route_agent_node(state)` wrapping calculate_route + origin/destination ValueError guard (D-10) | VERIFIED | 137 lines, state.get() reads origin/destination, raises ValueError if missing. |
| `backend/tests/test_fetch_fuel_price.py` | 6 tests using pytest-httpx | VERIFIED | 6 test functions, uses `httpx_mock` fixture (pytest-httpx). |
| `backend/tests/test_calculate_route.py` | 8+ tests | VERIFIED | 8 test functions including parametrised bucketing. |
| `backend/tests/test_lookup_rate.py` | 8 tests | VERIFIED (minor) | 8 test functions present and passing; file is 66 lines vs planned min 80 (test-dense but complete coverage). |
| `backend/tests/test_calculate_surcharge_tool.py` | 4 tests | VERIFIED | 4 test functions. |
| `backend/tests/test_fuel_agent.py` | 4 tests | VERIFIED | 4 test functions, uses FakeMessagesListChatModel. |
| `backend/tests/test_route_agent.py` | 5 tests | VERIFIED | 5 test functions, uses FakeMessagesListChatModel. |

### Key Link Verification

Automated gsd-tools key-link verification flagged several links as "not found" — these were false positives due to multi-line imports, pathlib `/` path construction, and comment-only matches confusing the single-line regex. All links confirmed manually via Grep.

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `backend/agent/state.py` | `operator.add` reducer | Annotated declaration | WIRED | Line 35: `reasoning_trace: Annotated[List[dict], operator.add]` — exact match. |
| `backend/tests/conftest.py` | `backend/tests/fixtures/` | fixture file reads | WIRED | Uses `_FIXTURES_DIR / "eppo_sample.html"` etc. pathlib form; all 5 files read. |
| `backend/agent/tools/fetch_fuel_price.py` | `FuelData` | pydantic model import | WIRED | Line 20: `from backend.agent.tools.models import FuelData`. |
| `backend/agent/tools/fetch_fuel_price.py` | `BASELINE_DIESEL_PRICE` | config import | WIRED | Line 21: `from backend.config import BASELINE_DIESEL_PRICE, FUEL_FETCH_TIMEOUT`. |
| `backend/agent/tools/fetch_fuel_price.py` | `data/raw/eppo_diesel_prices.csv` | pandas.read_csv via `_FUEL_CSV` | WIRED | Line 28: `_FUEL_CSV = _REPO_ROOT / "data" / "raw" / "eppo_diesel_prices.csv"`; `pd.read_csv(_FUEL_CSV)` at line 111. |
| `backend/agent/tools/calculate_route.py` | `googlemaps.Client` | lazy `_client()` | WIRED | Line 36 annotation + line 43 `googlemaps.Client(key=...)`. |
| `backend/agent/tools/calculate_route.py` | `data/raw/zone_definitions.json` | import-time zone index | WIRED | Line 33 path + line 57 `open(_ZONE_JSON)`. |
| `backend/agent/tools/calculate_route.py` | `backend/agent/tools/_cache.py` | TTLCache import | WIRED | Line 20: `from backend.agent.tools._cache import TTLCache`. |
| `backend/agent/tools/calculate_route.py` | `TRAFFIC_RATIO_BUCKETS` | config import | WIRED | Line 25 in multi-line import. |
| `backend/agent/tools/lookup_rate.py` | `data/express.db` | sqlite3.connect(DATABASE_PATH) | WIRED | Line 19: `_DB_PATH = Path(DATABASE_PATH)`; line 55 `sqlite3.connect(_DB_PATH)`. |
| `backend/agent/tools/lookup_rate.py` | `rate_table` | SELECT query | WIRED | Lines 47-52: SELECT ... FROM rate_table with half-open WHERE. |
| `backend/agent/tools/calculate_surcharge_tool.py` | Phase 1 `calculate_surcharge` pure function | import + delegate | WIRED | Lines 11-13: multi-line `from backend.agent.tools.calculate_surcharge import (calculate_surcharge as _calc,)`; used at line 44. |
| `backend/agent/nodes/fuel_agent.py` | `backend/agent/tools/fetch_fuel_price.py` | direct import + call | WIRED | Line 18 import; line 110 invocation. |
| `backend/agent/nodes/route_agent.py` | `backend/agent/tools/calculate_route.py` | direct import + call | WIRED | Line 22 import; line 117 invocation. |
| `backend/agent/nodes/fuel_agent.py` | `backend/agent/llm.get_chat_model` | factory call (patchable) | WIRED | Line 16 import; line 76 call inside `_narrate_with_llm`. |
| `backend/agent/nodes/route_agent.py` | `backend/agent/llm.get_chat_model` | factory call (patchable) | WIRED | Line 20 import; line 72 call inside `_narrate_with_llm`. |

### Data-Flow Trace (Level 4)

Verified that data actually flows from sources through the artifacts. Phase 2 produces library code (tools + nodes) rather than end-user-facing components, so Level 4 focused on data pipelines.

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `fetch_fuel_price()` | `FuelData.price` | `data/raw/eppo_diesel_prices.csv` (Level 2) | Yes — smoke test returned 31.62 from real 185-row CSV | FLOWING |
| `calculate_route()` | `RouteData.zone` | `data/raw/zone_definitions.json` + googlemaps.geocode | Yes — tests verify all 3 zones produced from captured fixtures; live mode flows through real Google Maps (not exercised in tests, which is correct per budget constraint) | FLOWING (tests use fixtures) |
| `lookup_rate()` | `RateResult.base_rate` | `data/express.db` rate_table | Yes — smoke test returned real 85.0 THB (bounce/central-1/5-10kg tier) and 698.0 THB (retail_fast/central-3/50+kg tier) | FLOWING |
| `calculate_surcharge_tool.invoke()` | `SurchargeResult` | Phase 1 pure function + SurchargeInput schema | Yes — smoke test returned surcharge_pct=0.0344 for a full invocation with args_schema validation | FLOWING |
| `fuel_agent_node(state)` | `state['fuel_data']` + trace entry | fetch_fuel_price + Gemini narration | Yes — smoke test with real state produced fuel_data (source=eppo_cached_csv) + D-12 trace entry; Gemini auth unavailable triggered deterministic fallback path (working as designed) | FLOWING |
| `route_agent_node(state)` | `state['route_data']` + trace entry | calculate_route(origin, destination) + Gemini narration | Yes — tests verify state update with mocked RouteData including zone="central-1" | FLOWING (mocked) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full test suite passes | `.venv/bin/pytest backend/tests/ -v` | 74 passed, 0 failed, 0.77s | PASS |
| fetch_fuel_price returns structured Pydantic response | `python -c "from backend.agent.tools.fetch_fuel_price import fetch_fuel_price; r=fetch_fuel_price(); print(type(r).__name__, r.source)"` | `FuelData eppo_cached_csv` | PASS |
| lookup_rate queries real SQLite | `python -c "from backend.agent.tools.lookup_rate import lookup_rate; r=lookup_rate('bounce','central-1',7.5); print(r.base_rate, r.rate_tier)"` | `85.0 5-10kg` | PASS |
| calculate_surcharge_tool is a @tool with args_schema | `python -c "from backend.agent.tools.calculate_surcharge_tool import calculate_surcharge_tool as t; print(t.name, t.args_schema.__name__)"` | `calculate_surcharge SurchargeInput` | PASS |
| TTLCache get/set/clear works | `python -c "from backend.agent.tools._cache import TTLCache; c=TTLCache(10); c.set('k','v'); print(c.get('k')); c.clear(); print(c.get('k'))"` | `v` then `None` | PASS |
| fuel_agent_node invokable with AgentState | `python -c "from backend.agent.nodes.fuel_agent import fuel_agent_node; r=fuel_agent_node({...sample state...}); print(list(r.keys()), sorted(r['reasoning_trace'][0].keys()))"` | Returns `['fuel_data','reasoning_trace']` with all 8 D-12 keys and status=ok | PASS |
| All Phase 2 deps importable | `python -c "import langgraph, langchain_google_genai, googlemaps, httpx, pytest_httpx, pytest_mock"` | No error | PASS |

### Requirements Coverage

Requirement IDs extracted from plan frontmatter and cross-referenced with REQUIREMENTS.md.

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| TOOL-01 | 02-02-PLAN.md | fetch_fuel_price tool retrieves live diesel price with multi-level fallback | SATISFIED | `backend/agent/tools/fetch_fuel_price.py` implements Level 1 (stubbed per Open Question 2 — Phase 5 polish), Level 2 CSV, Level 3 baseline. 6 passing tests verify all paths and backoff [1, 2]. |
| TOOL-02 | 02-03-PLAN.md | calculate_route tool via Google Maps with 15-min caching | SATISFIED | `backend/agent/tools/calculate_route.py` uses `googlemaps.Client`, TTLCache(ttl=900s), zone derivation via `zone_definitions.json`. 12 passing tests. |
| TOOL-03 | 02-04-PLAN.md | lookup_rate queries SQLite rate table | SATISFIED | `backend/agent/tools/lookup_rate.py` runs parameterised half-open SQL against `data/express.db`. 8 passing tests. |
| TOOL-04 | 02-04-PLAN.md | calculate_surcharge tool applies formula with traffic + cap | SATISFIED | `backend/agent/tools/calculate_surcharge_tool.py` wraps Phase 1 pure function as LangChain @tool with `args_schema=SurchargeInput`. 4 passing tests including parity with pure function. |
| ORCH-02 | 02-05-PLAN.md | Fuel Agent node wraps fetch_fuel_price | SATISFIED | `backend/agent/nodes/fuel_agent.py` implements `fuel_agent_node(state)` with Gemini narration + D-11 deterministic fallback. search_fuel_news intentionally excluded per Open Question 3 (Phase 5). 4 passing tests. |
| ORCH-03 | 02-05-PLAN.md | Route Agent node wraps calculate_route with zone mapping | SATISFIED | `backend/agent/nodes/route_agent.py` implements `route_agent_node(state)` reading origin/destination from state (D-10), raising ValueError on missing inputs. 5 passing tests. |

All 6 required requirement IDs satisfied. No orphaned requirements — REQUIREMENTS.md maps TOOL-01..04 and ORCH-02/03 to Phase 2 and all are covered by the plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `backend/agent/tools/fetch_fuel_price.py` | 100 | `raise NotImplementedError("scrape selectors: capture live HTML first")` | Info | Intentional stub for Level 1 live scrape per Open Question 2 (deferred to Phase 5 polish). Fallback chain designed so this does not block goal — CSV fallback returns real data. Documented in plan, summary, code comment, docstring, and caught explicitly by the Level 1 except clause. |

No TODO/FIXME/XXX/HACK markers found anywhere in `backend/agent/`. No placeholder strings. No empty handlers. No hardcoded empty data in production code paths (fixtures excluded per convention). No `console.log`-only implementations.

### Deviations From Plan

1. **Plan 02-05: Replaced `with_structured_output()` with raw `.invoke()` + JSON parsing** — Plan prescribed `model.with_structured_output(FuelReasoning, method="json_schema")` but `FakeMessagesListChatModel` used in tests does not implement that helper. Switched to plain chat invocation + `_parse_structured` that strips Markdown fences and validates via Pydantic. Broad try/except preserves D-11 fallback contract. Documented in 02-05-SUMMARY.md as "Rule 1 bug fix" — required for the plan's own tests to pass. Core intent (Gemini narration + D-11 fallback + D-12 trace) preserved verbatim. **Not a gap.**

2. **test_lookup_rate.py 66 lines vs min 80 planned** — File contains all 8 required test functions and all tests pass. Test is concise rather than verbose. Minor deviation, not a gap.

### Human Verification Required

None. All 4 Success Criteria verified programmatically via the 74-test suite and direct smoke invocations. Tests cover every observable behavior specified in the phase goal. The only items Phase 2 does not exercise are (a) live EPPO scrape (intentionally stubbed) and (b) live Google Maps API (tests use captured fixtures — correct under the $200-credit budget constraint). These are handled in Phase 5 polish.

### Gaps Summary

**No gaps.** Phase 2 goal fully achieved:

- Each of the four tools (fetch_fuel_price, calculate_route, lookup_rate, calculate_surcharge_tool) works independently with passing tests.
- Two agent nodes (fuel_agent_node, route_agent_node) wrap their tools in LangGraph-compatible callables that consume AgentState and return partial state updates with D-12 reasoning_trace entries.
- LLM narration is test-swappable via the `get_chat_model` factory; D-11 deterministic fallback is proven by tests injecting broken LLMs.
- AgentState now uses `Annotated[List[dict], operator.add]` on `reasoning_trace` so parallel nodes in Phase 5 can each append without stomping writes.
- All 6 Phase 2 requirement IDs (TOOL-01..04, ORCH-02, ORCH-03) satisfied; 74/74 tests pass.

Phase 3 (Graph Assembly & API Layer) is unblocked: the Planner node can wire fuel_agent_node and route_agent_node into a StateGraph, and the established D-12 trace schema + `get_chat_model` seam are ready for reuse by the Pricing Agent (ORCH-04) and Planner (ORCH-01).

---

_Verified: 2026-04-18T08:07:29Z_
_Verifier: Claude (gsd-verifier)_
