# Phase 2: Tools & Agent Nodes - Research

**Researched:** 2026-04-18
**Domain:** LangGraph tools & nodes, Gemini structured output, Google Maps client, EPPO scraping with fallback, SQLite rate lookup, test mocking for HTTP + LLM
**Confidence:** HIGH (stack + patterns verified via official docs; MEDIUM on EPPO scrape resilience and on the exact shape of Gemini structured-output failures)

## Summary

Phase 2 wraps four tools and two agent nodes on top of the Phase 1 foundation (Pydantic models, `AgentState` TypedDict, pure `calculate_surcharge`, seeded `express.db`, zone JSON, EPPO seed CSV). The work is moderate-complexity because Phase 1 already nailed the types and the pure logic — Phase 2 is about idiomatic LangGraph wrappers, external API integration with disciplined mocking, and the first real LLM calls.

CONTEXT.md locks almost every architectural choice (httpx + BeautifulSoup for scraping, `googlemaps` client for Maps, 3-level fuel fallback chain, LLM-wrapped tool calls for the Fuel/Route agents, half-open weight-tier intervals, in-process 15-minute route cache, structured reasoning-trace entries). Research confirms those choices are idiomatic and viable. Two CONTEXT.md assumptions need correction before planning — see **Blockers / Corrections** below.

**Primary recommendation:** Build in this order — (1) `fetch_fuel_price` tool + tests (exercises the hardest design: fallback chain, retry, source tagging), (2) `calculate_route` tool + tests with pre-captured Google Maps JSON fixtures, (3) `lookup_rate` tool + in-memory SQLite fixture tests, (4) `calculate_surcharge` LangGraph `@tool` wrapper (trivial — wraps the existing pure function, reuses existing tests), (5) `fuel_agent_node` + `route_agent_node` with `FakeMessagesListChatModel` scripting Gemini tool-call responses. Prove the Gemini structured-output pattern end-to-end on the first agent node — that resolves the "Gemini reliability unknown" blocker in STATE.md.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Fuel fetch fallback chain (TOOL-01)**
- **D-01:** Three-level chain: live EPPO scrape → latest row in `data/raw/eppo_diesel_prices.csv` → `BASELINE_DIESEL_PRICE` constant. No PTT secondary scrape — reality is that EPPO has no public API, so "API → scrape" collapses to scrape-only as the live path.
- **D-02:** HTTP client is `httpx` (async-native, FastAPI/LangGraph-compatible) with `BeautifulSoup4` for HTML parsing.
- **D-03:** Expand `FuelData.source` enum beyond Phase 1's `eppo`/`ptt` values. New values used by the tool: `eppo_live`, `eppo_cached_csv`, `hardcoded_baseline`. Reasoning trace renders the exact level hit.
- **D-04:** Live-fetch retry policy inside the tool: 2 retries with exponential backoff (1s, then 2s) before falling to CSV. Aligned with ORCH-08 direction without depending on the Phase 3 agentic wrapper.

**Route tool & zone mapping (TOOL-02, ORCH-03)**
- **D-05:** Zone derivation: reverse-geocode the **destination** via Google Maps Geocoding API, extract `administrative_area_level_1` (province), match against `data/raw/zone_definitions.json` to produce `central-1`/`central-2`/`central-3`. Deterministic, testable, respects TOOL-06 (structured output).
- **D-06:** Traffic severity (1-5) derived from **ratio** `duration_in_traffic / duration`, bucketed: `<1.1=1`, `1.1-1.3=2`, `1.3-1.5=3`, `1.5-1.8=4`, `>1.8=5`. Thresholds live in `backend/config.py` so tuning does not require code changes.
- **D-07:** 15-minute route cache is in-process: a `(origin, destination)` → `(RouteData, timestamp)` dict behind a TTL wrapper. Resets on server restart — acceptable for dev + demo. No SQLite persistence.
- **D-08:** Dev hits Google Maps live; tests use pre-recorded JSON fixtures (no live API calls in CI).

**Agent node reasoning style (ORCH-02, ORCH-03)**
- **D-09:** LLM-wrapped tool calls in Fuel Agent and Route Agent nodes. Each node: Gemini receives state + system prompt, decides to call its tool with extracted args, Gemini summarises the tool result into a `reasoning_trace` entry, node updates state.
- **D-10:** Nodes read **pre-extracted** fields from `AgentState` (`shipping_type`, `weight_kg`, origin/destination placeholders). Planner (Phase 3) is responsible for extraction. Phase 2 tests pass state directly.
- **D-11:** Gemini structured-output fallback: if the Gemini response doesn't parse into the expected Pydantic model, retry once with a stricter prompt; if the second attempt still fails, skip LLM narration and emit a canned deterministic `reasoning_trace` entry from the tool result.
- **D-12:** `reasoning_trace` entry schema: `{step, agent, tool, tool_input, tool_output, reasoning, timestamp, status}`. Maps 1:1 to Langfuse spans (Phase 5) and UI-02 trace panel (Phase 4).

**lookup_rate tool (TOOL-03)**
- **D-13:** Weight tier lookup uses **half-open intervals** `[weight_min_kg, weight_max_kg)`. SQL: `WHERE weight_min_kg <= :w AND (weight_max_kg IS NULL OR :w < weight_max_kg)`. Top tier (`50+`) stores `weight_max_kg = NULL`. 5.0 kg falls in the `5-10` tier, not `0-5`.
- **D-14:** On lookup miss (unknown zone, weight above top tier, unknown shipping_type), the tool raises `ValueError` with descriptive context. Phase 3 Planner/Pricing nodes catch and route to the clarify path — Phase 2 tests verify the exception.

**Testing strategy (cross-cutting)**
- **D-15:** External HTTP mocked via the `responses` library (for `requests` / `httpx`-adapter mode). One-time capture of real EPPO HTML + Google Maps JSON committed as fixtures. Tests run offline and deterministically.
- **D-16:** Agent-node tests mock the LLM via `langchain` `FakeListChatModel` / `FakeMessagesListChatModel` — scripted Gemini responses, zero quota consumption.

### Claude's Discretion
- Exact module layout for the new tools (file names, test file names) as long as it follows `backend/agent/tools/<name>.py` + `backend/tests/test_<name>.py`.
- Config keys and defaults for traffic-ratio thresholds (within the D-06 bucketing rule).
- Choice of `requests`-adapter vs native `httpx.MockTransport` inside the `responses` setup. **See Correction C-01 below** — `responses` does not support httpx; must substitute `respx` or `pytest-httpx`.
- Internal structure of the TTL wrapper (D-07) — class, context manager, or decorator.
- Format of Gemini system prompts for Fuel and Route agents (must produce structured output parseable to Pydantic).

### Deferred Ideas (OUT OF SCOPE)
- `search_fuel_news` tool (TOOL-05) — Phase 5. Fuel Agent system prompt (D-09) may *mention* it but the tool itself is not implemented here.
- Planner node / intent extraction — Phase 3. Fuel/Route agents rely on pre-extracted state (D-10).
- Agentic retry loop with exponential backoff + graceful fallback (ORCH-08) — Phase 3. Phase 2's in-tool retry (D-04) is a local stand-in.
- Human-in-the-loop approval gate (ORCH-09) — Phase 5.
- Parallel Fuel + Route execution via LangGraph Send API (ORCH-07) — Phase 5.
- Conversation memory via SQLite checkpointer (ORCH-10) — Phase 3.
- Pricing Agent node wrapping `lookup_rate` + `calculate_surcharge` (ORCH-04) — Phase 3.
- Langfuse callback integration (OBS-01) — Phase 5. Trace schema (D-12) is pre-aligned.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | `fetch_fuel_price` returns current diesel price via multi-level fallback chain (live scrape → cached CSV → baseline constant) with structured Pydantic response | Standard stack (httpx + BeautifulSoup + pandas), pathlib-relative CSV read pattern from Phase 1, source-enum expansion in `FuelData` (D-03), retry pattern (exponential backoff), `respx`/`pytest-httpx` for test mocks (see C-01) |
| TOOL-02 | `calculate_route` returns distance, duration, traffic severity, zone via Google Maps Directions + Geocoding, with 15-minute in-process cache | `googlemaps` 4.10.0 client — `directions()` + `reverse_geocode()`, `administrative_area_level_1` extraction pattern, traffic-ratio bucketing (D-06), TTL dict for cache, JSON fixture capture strategy |
| TOOL-03 | `lookup_rate` queries SQLite rate table by `shipping_type + zone + weight_kg`, returns `RateResult` | sqlite3 stdlib (already used by seed script), parameterised SQL with half-open tier intervals (D-13), `ValueError` on miss (D-14), in-memory SQLite fixture for tests |
| TOOL-04 | `calculate_surcharge` tool wraps the existing pure function as a LangGraph `@tool` | LangChain `@tool` decorator with `args_schema=SurchargeInput`, reuses `calculate_surcharge.py` unchanged, reuses existing 13 test cases via the wrapper |
| ORCH-02 | Fuel Agent node wraps `fetch_fuel_price` (and stubs `search_fuel_news`), invokable with sample `AgentState`, produces state updates + reasoning trace | LangGraph node signature `State -> Partial<State>`, `ChatGoogleGenerativeAI` from `langchain-google-genai`, `.bind_tools([...])` + `.with_structured_output()` pattern, reasoning-trace entry (D-12), `FakeMessagesListChatModel` for tests (D-16) |
| ORCH-03 | Route Agent node wraps `calculate_route`, invokable with sample `AgentState`, produces state updates + reasoning trace | Same LangGraph node pattern as Fuel Agent; consumes Route tool; reads pre-extracted origin/destination from state (D-10) |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Budget:** Free-tier APIs only — Gemini 2.0 Flash, Google Maps ($200/mo credit), EPPO public data. No paid model APIs.
- **LLM:** Gemini 2.0 Flash only. Gemini free tier is 15 RPM — tests must NOT hit live Gemini (D-16 mandatory, not optional).
- **Python conventions:** PEP 8, Black (88 char), Google-style docstrings on every public function, type hints on all signatures, `from __future__ import annotations` for modern type syntax compatibility.
- **File locations:** tools in `backend/agent/tools/<name>.py`, nodes in `backend/agent/nodes/<name>.py`, tests in `backend/tests/test_<name>.py`, prompts in `backend/agent/prompts/<name>.py`.
- **Naming:** Module files `snake_case.py`; classes `PascalCase`; variables/functions `snake_case`; constants `UPPER_CASE`. Node names `<agent>_node` (e.g., `fuel_agent_node`). Next-step routing values lowercase with underscores.
- **Exceptions:** Specific exception types (not bare `except`). Include context in messages. Pure functions raise `ValueError` with descriptive messages (Phase 1 D-11 pattern — `lookup_rate` inherits).
- **Secrets:** `.env` is gitignored. `.env.example` already has `GOOGLE_API_KEY`, `GOOGLE_MAPS_API_KEY`, `TAVILY_API_KEY`, `LANGFUSE_*`. Phase 2 does not add new keys.
- **Logging:** Tool invocations (start + result), cache hits/misses, fallback-chain level hit, errors with full context — structured logging via stdlib `logging`. No `print()` in library code.
- **Data paths:** `pathlib.Path(__file__).parent` relative to module for all data-file reads (Phase 1 accumulated decision). Never assume cwd.
- **GSD:** All changes via GSD commands. Descriptive commits, feature branches.

## Blockers / Corrections to CONTEXT.md

Surface these to the planner **before** tasks are drafted — each is a small but real conflict between CONTEXT.md and the code / ecosystem reality.

### C-01 (HIGH confidence) — `responses` library does NOT support httpx

**CONTEXT.md D-02** selects `httpx` as the HTTP client. **CONTEXT.md D-15** prescribes the `responses` library for mocking. These are incompatible: `responses` (v0.26.0, active) is built to patch the `requests` library only. It has no httpx transport.

**Three viable substitutes for httpx mocking (pick one):**

| Library | Version | Fit | Notes |
|---------|---------|-----|-------|
| `pytest-httpx` | 0.35.0 | **Recommended** — pytest-native fixture, minimal boilerplate, sync + async | `httpx_mock.add_response(url=..., html=...)` |
| `respx` | 0.23.1 | Powerful URL patterns, side-effect routes | Slightly more API surface than needed for our case |
| `httpx.MockTransport` | built-in | Zero deps | Most verbose — good for one-off cases |

**Recommendation:** `pytest-httpx` — it's the closest API analogue to what CONTEXT.md meant by `responses`, is small, sync+async, and has a pytest fixture that drops into existing `backend/tests/`. Document this as an update to D-15 in the plan.

**If Phase 2 instead switches off httpx to `requests`** (CONTEXT.md already says httpx is for "async-native, FastAPI/LangGraph-compatible" use — but our fuel scraper is a synchronous one-shot, so `requests` would also work and would let `responses` be used verbatim): that is a valid alternative. Raise with the user at plan-check time.

### C-02 (HIGH confidence) — Rate table does NOT have NULL for top tier

**CONTEXT.md D-13** says: "The top tier (`50+`) stores `weight_max_kg = NULL`." **Verified in DB** (`sqlite3 data/express.db "SELECT * FROM rate_table WHERE weight_min_kg=50"`): all 9 top-tier rows have `weight_max_kg = 999` (integer sentinel), not NULL. The Phase 1 `generate_rate_table.py` used `WEIGHT_TIERS = [..., (50, 9999)]` but the committed CSV shows `50,999` — still a sentinel, not NULL.

**Two options:**

1. **Change the SQL to handle the sentinel** (no data migration needed):
   ```sql
   WHERE shipping_type = :st AND zone = :z
     AND weight_min_kg <= :w
     AND :w < weight_max_kg   -- 999 or 9999 both work as sentinels
   ```
   This keeps the CSV/DB as-is. `lookup_rate` works for weights up to 998 kg. Document "weight > 998 raises ValueError" as a real limit.

2. **Migrate the DB to use NULL for the top tier** (faithful to D-13 intent):
   - Add a one-line update in `seed_database.py`: `UPDATE rate_table SET weight_max_kg = NULL WHERE weight_max_kg = 999`
   - Re-seed: `python data/scripts/seed_database.py`
   - Adopt the D-13 SQL verbatim.

**Recommendation:** Option 1 (handle sentinel). Rationale: (a) it's a one-line SQL difference, (b) it avoids changing a Phase 1 artifact, (c) `lookup_rate` can still raise `ValueError` for weights > 998 to match D-14, (d) the CSV stays human-readable. If the user prefers purity, Option 2 is trivial.

### C-03 (MEDIUM confidence) — `.venv` is Python 3.9.6, not 3.11+

CLAUDE.md stack spec says Python 3.11+. The committed `.venv` points at `/Library/Developer/CommandLineTools/.../Versions/3.9/bin/python3` (macOS Command Line Tools default). No `python3.11`/`python3.12` is installed on the machine. Phase 1 code works on 3.9 only because every module has `from __future__ import annotations` and `AgentState` uses `Optional[...]` / `List[...]` (not `dict | None`).

**Why this is a Phase 2 concern now, not just a style nit:**
- `langgraph` 0.6.11 requires Python >= 3.9 — compatible.
- `langchain-core` 0.3.84 requires Python >= 3.9 — compatible.
- `langchain-google-genai` 2.1.12 requires Python >= 3.9 — compatible.
- `googlemaps` 4.10.0 requires Python >= 3.5 — compatible.
- `httpx` 0.28.1 requires Python >= 3.8 — compatible.

**No install-time blocker exists.** All Phase 2 libraries install cleanly on 3.9.6. The planner should note that `AgentState.messages` currently types as `List[dict]` (deferred to Phase 2 per Phase 1 Open Question 2 — time to upgrade to `List[BaseMessage]` if the Fuel/Route agent nodes need it, OR keep `List[dict]` and serialise at node boundaries).

**Recommendation:** Stay on the existing venv for Phase 2. Do NOT break Phase 1 tests by requiring 3.11. If 3.11 becomes needed for Phase 3 (SQLite checkpointer, FastAPI) we can upgrade then. Document the tension in the plan but don't block on it.

## Standard Stack

**Version verification (via `pip index versions` on 2026-04-18):**

### Core (new in Phase 2)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langgraph` | 0.6.11 | Graph orchestration; provides `StateGraph`, node registration | Phase 2 doesn't build the graph yet but we import types and match the node signature contract |
| `langchain-core` | 0.3.84 | `BaseMessage`, `AIMessage`, `HumanMessage`, `SystemMessage`, `FakeMessagesListChatModel`, `@tool` decorator | Required by langgraph and langchain-google-genai; already a transitive of langgraph |
| `langchain-google-genai` | 2.1.12 | `ChatGoogleGenerativeAI` Gemini chat-model wrapper | Official LangChain Gemini integration; supports `bind_tools()` + `with_structured_output()` — the two patterns D-09/D-11 require |
| `googlemaps` | 4.10.0 | Python client for Directions + Geocoding APIs | Official Google-maintained client. Note: last release Jan 2023 (stagnant but stable; still the idiomatic choice) |
| `httpx` | 0.28.1 | Async-capable HTTP client for EPPO scrape (D-02) | Successor to `requests`; async-native for future FastAPI use |

### Supporting (new in Phase 2)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest-httpx` | 0.35.0 | Pytest fixture to mock httpx requests | **Replaces `responses` per C-01** — fuel scrape tests |
| `pytest-mock` | 3.15.1 | `mocker` fixture for arbitrary `unittest.mock.patch` shortcuts | Patching `googlemaps.Client` in route tests |
| `tenacity` | latest | Declarative retry with exponential backoff | **Optional** — D-04 retry logic is simple enough to hand-write; include only if you want a clean `@retry` decorator |

### Already installed (Phase 1) and reused
| Library | Version | Used For |
|---------|---------|----------|
| `pydantic` | 2.12.5 | All tool I/O models (from `backend/agent/tools/models.py`) |
| `beautifulsoup4` | 4.14.3 | Parse EPPO HTML (D-02) |
| `pandas` | 2.3.3 | Read `eppo_diesel_prices.csv` fallback (Phase 1 uses pandas — staying consistent) |
| `requests` | 2.32.5 | NOT used by new code. Kept for Phase 1's `fetch_fuel_prices.py` script. |
| `python-dotenv` | 1.1.1 | `.env` loading via existing `backend/config.py` |
| `pytest` | 8.4.2 | All new test files |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx` (D-02) | `requests` | `responses` works with `requests`, saving C-01. But CONTEXT.md explicitly picks httpx for FastAPI-async-future alignment — stay the course and swap the mock library. |
| `langchain-google-genai` | `google-generativeai` SDK directly | CLAUDE.md lists `google-generativeai` in Key Dependencies. But `ChatGoogleGenerativeAI` is what integrates with `@tool`, `FakeMessagesListChatModel`, and LangGraph. Using the raw SDK loses `bind_tools()` / `with_structured_output()` and requires hand-rolled JSON parsing. **Use `langchain-google-genai` for LangGraph agent nodes; keep `google-generativeai` transitive-only.** |
| `pytest-httpx` | `respx` | Both work. `pytest-httpx` is slightly simpler and pytest-idiomatic. |
| In-process TTL dict (D-07) | `cachetools.TTLCache` | `cachetools` is 50 lines of Python we don't need; a tiny custom class is clearer and testable. |

**Installation (append to `requirements.txt`):**
```bash
# Phase 2 additions
langgraph==0.6.11
langchain-core==0.3.84
langchain-google-genai==2.1.12
googlemaps==4.10.0
httpx==0.28.1
pytest-httpx==0.35.0
pytest-mock==3.15.1
```

## Architecture Patterns

### Recommended Project Structure (additions to Phase 1 layout)
```
backend/
  agent/
    tools/
      fetch_fuel_price.py        # NEW — tool + fallback chain (TOOL-01)
      calculate_route.py         # NEW — tool + zone derivation + cache (TOOL-02)
      lookup_rate.py             # NEW — SQLite query tool (TOOL-03)
      calculate_surcharge_tool.py # NEW — @tool wrapper around Phase 1 pure fn (TOOL-04)
      _cache.py                  # NEW — small in-process TTL helper (D-07)
      calculate_surcharge.py     # (Phase 1 — unchanged)
      models.py                  # (Phase 1 — add FuelSource enum values per D-03)
    nodes/
      fuel_agent.py              # NEW — ORCH-02 node (fuel_agent_node)
      route_agent.py             # NEW — ORCH-03 node (route_agent_node)
    prompts/
      fuel_agent.py              # NEW — Gemini system prompt for fuel agent
      route_agent.py             # NEW — Gemini system prompt for route agent
    llm.py                       # NEW — thin factory for ChatGoogleGenerativeAI + test-time swap
  config.py                      # MODIFIED — add TRAFFIC_RATIO_THRESHOLDS, GEMINI_MODEL, FUEL_FETCH_TIMEOUT, ROUTE_CACHE_TTL_SECONDS
  tests/
    conftest.py                  # NEW — shared fixtures (sample AgentState, temp SQLite, fake LLM, etc.)
    fixtures/
      eppo_sample.html           # NEW — captured EPPO HTML sample for offline tests
      gmaps_directions.json      # NEW — captured Google Maps Directions response
      gmaps_geocode_bangkok.json # NEW — captured reverse-geocode response
      express_test.db            # OPTIONAL — seeded test DB (or build in-memory per test)
    test_fetch_fuel_price.py     # NEW — TOOL-01 tests
    test_calculate_route.py      # NEW — TOOL-02 tests
    test_lookup_rate.py          # NEW — TOOL-03 tests
    test_calculate_surcharge_tool.py # NEW — TOOL-04 wrapper tests
    test_fuel_agent.py           # NEW — ORCH-02 node tests
    test_route_agent.py          # NEW — ORCH-03 node tests
```

### Pattern 1: LangGraph node function signature

**What:** A node is a plain callable `(state: AgentState) -> dict`. LangGraph merges the returned dict into state via the state's reducer rules. Nodes return ONLY the fields they change.

**Source:** https://docs.langchain.com/oss/python/langgraph/use-graph-api — "The signature of each node is `State -> Partial<State>`."

**When to use:** Every agent node in `backend/agent/nodes/`.

**Example (Fuel Agent node skeleton):**
```python
# backend/agent/nodes/fuel_agent.py
from __future__ import annotations

from datetime import datetime
import logging

from backend.agent.state import AgentState
from backend.agent.tools.fetch_fuel_price import fetch_fuel_price
from backend.agent.llm import get_chat_model
from backend.agent.prompts.fuel_agent import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def fuel_agent_node(state: AgentState) -> dict:
    """Fuel Agent node: fetches current diesel price and narrates reasoning.

    Args:
        state: Full AgentState dict (read-only from this node's perspective).

    Returns:
        Partial state dict with fuel_data and a new reasoning_trace entry.
        LangGraph merges this into the outer state.
    """
    # 1. Call the tool directly (no LLM round-trip yet).
    fuel_data = fetch_fuel_price()  # returns FuelData Pydantic model

    # 2. Ask Gemini to produce a reasoning sentence (D-09).
    reasoning = _narrate_with_llm(state, fuel_data)

    # 3. Build a D-12 trace entry.
    trace_entry = {
        "step": len(state.get("reasoning_trace", [])) + 1,
        "agent": "fuel_agent",
        "tool": "fetch_fuel_price",
        "tool_input": {},
        "tool_output": fuel_data.model_dump(),
        "reasoning": reasoning,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "status": "ok",
    }

    # 4. Return only fields we updated. reasoning_trace returned as a
    #    single-element list — if state.py adds an Annotated reducer later,
    #    LangGraph will append; otherwise the caller is responsible.
    return {
        "fuel_data": fuel_data.model_dump(),
        "reasoning_trace": state.get("reasoning_trace", []) + [trace_entry],
    }
```

**Important:** The current `AgentState` (`backend/agent/state.py`) uses plain `List[dict]` for `reasoning_trace` with NO `Annotated[..., reducer]`. That means LangGraph's default reducer is **replace, not append**. Either (a) change `AgentState.reasoning_trace` to `Annotated[List[dict], operator.add]` (additive, proper LangGraph idiom), or (b) have each node manually concatenate the prior list and return the whole thing (shown above, works but brittle). **Recommend (a).** This is a small change to Phase 1's `state.py` and should happen in Wave 0 of Phase 2.

### Pattern 2: Gemini with `bind_tools()` + `with_structured_output()`

**What:** Two separate Gemini calls per agent node — first to pick/format the tool call, second (optional) to narrate the result as structured JSON.

**Source:** https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai — confirmed syntax for `bind_tools()` and `with_structured_output(schema=..., method="json_schema")`.

**When to use:** The fuel/route nodes per D-09. Keep the "LLM decides tool args" ceremony minimal — Phase 2 state pre-extracts everything, so in practice the first Gemini call is almost redundant and exists mainly for the "visible reasoning" grading value.

**Example:**
```python
# backend/agent/llm.py
from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI

from backend.config import GEMINI_MODEL  # "gemini-2.0-flash" from .env


def get_chat_model(**overrides) -> ChatGoogleGenerativeAI:
    """Factory for the project's Gemini chat model. Tests monkey-patch this."""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0.0,  # deterministic for tests and consistent reasoning
        max_retries=0,    # we handle retries ourselves per D-11
        **overrides,
    )


# backend/agent/nodes/fuel_agent.py (continuing)
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage


class FuelReasoning(BaseModel):
    """Structured narration schema for the Fuel Agent (D-11)."""
    summary: str = Field(description="One-sentence summary of the fuel price")
    trend: str = Field(description="above_baseline | below_baseline | at_baseline")


def _narrate_with_llm(state: AgentState, fuel_data) -> str:
    model = get_chat_model()
    structured = model.with_structured_output(FuelReasoning, method="json_schema")
    try:
        out = structured.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Tool returned: {fuel_data.model_dump_json()}"),
        ])
        return f"{out.summary} ({out.trend})"
    except Exception as e:
        logger.warning("Gemini narration failed, using deterministic fallback: %s", e)
        # D-11 fallback: canned trace, no LLM narration
        direction = "above" if fuel_data.delta_pct > 0 else "below"
        return (
            f"Current diesel B7 is {fuel_data.price:.2f} THB/L "
            f"({abs(fuel_data.delta_pct):.2%} {direction} baseline)."
        )
```

### Pattern 3: `@tool` decorator with Pydantic `args_schema`

**What:** Turn any Python function into a LangChain Tool by decorating it. The `args_schema` parameter makes the JSON schema explicit for Gemini's function-calling.

**Source:** https://docs.langchain.com/oss/python/langchain/tools ; field descriptions propagate into the JSON schema the LLM sees.

**When to use:** TOOL-04 (`calculate_surcharge_tool`) — wrap the existing pure function. OPTIONAL for the other three tools (they can also be plain callables; `@tool` only matters if an LLM needs to invoke them via function calling, which Phase 2 nodes mostly don't — they call the Python function directly and pass the result to the LLM for narration).

**Example:**
```python
# backend/agent/tools/calculate_surcharge_tool.py
from __future__ import annotations

from langchain_core.tools import tool

from backend.agent.tools.calculate_surcharge import calculate_surcharge as _calc
from backend.agent.tools.models import SurchargeInput, SurchargeResult


@tool("calculate_surcharge", args_schema=SurchargeInput)
def calculate_surcharge_tool(
    base_rate: float,
    current_diesel_price: float,
    shipping_type: str,
    traffic_severity: int = 1,
) -> SurchargeResult:
    """Calculate fuel surcharge for a shipment.

    Reuses the Phase 1 pure function. Pydantic input validation is handled
    by the SurchargeInput args_schema; ValueError from the inner function
    surfaces to the caller unchanged.
    """
    return _calc(base_rate, current_diesel_price, shipping_type, traffic_severity)
```

**Why this is trivial:** The pure function already has input validation and returns a Pydantic model. The wrapper just adds LangGraph surface area. Phase 1 tests (`test_surcharge.py`) still pass against the pure function; add a thin `test_calculate_surcharge_tool.py` that verifies `.invoke()` with a dict input works and returns the same `SurchargeResult`.

### Pattern 4: Multi-level fallback chain for `fetch_fuel_price`

**What:** Try each source in order; on any failure move to the next; tag the `FuelData.source` with which level actually served the data.

**When to use:** TOOL-01. Every external API Phase 2 calls should have a graceful fallback.

**Example:**
```python
# backend/agent/tools/fetch_fuel_price.py
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from backend.agent.tools.models import FuelData
from backend.config import BASELINE_DIESEL_PRICE, FUEL_FETCH_TIMEOUT

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FUEL_CSV = _REPO_ROOT / "data" / "raw" / "eppo_diesel_prices.csv"
_EPPO_URL = (
    "https://www.eppo.go.th/index.php/en/en-energystatistics"
    "/en-petroleum-statistic"
)


def fetch_fuel_price() -> FuelData:
    """Return current diesel B7 price via a 3-level fallback chain (D-01, D-04).

    Level 1: live EPPO scrape (with 2 retries, exponential backoff).
    Level 2: latest row in data/raw/eppo_diesel_prices.csv.
    Level 3: BASELINE_DIESEL_PRICE constant.

    Returns:
        FuelData with `source` ∈ {'eppo_live', 'eppo_cached_csv', 'hardcoded_baseline'}.
        Never raises — the baseline is always reachable.
    """
    # Level 1
    for attempt, backoff in enumerate([0, 1, 2]):
        if backoff:
            time.sleep(backoff)
        try:
            price, date = _scrape_eppo_live()
            return _build_fuel_data(price, date, "eppo_live")
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("EPPO scrape attempt %d failed: %s", attempt + 1, e)

    # Level 2
    try:
        price, date = _read_cached_csv()
        return _build_fuel_data(price, date, "eppo_cached_csv")
    except (FileNotFoundError, pd.errors.EmptyDataError, ValueError) as e:
        logger.warning("CSV fallback failed: %s", e)

    # Level 3 — always works
    return _build_fuel_data(
        BASELINE_DIESEL_PRICE,
        date=pd.Timestamp.utcnow().strftime("%Y-%m-%d"),
        source="hardcoded_baseline",
    )


def _build_fuel_data(price: float, date: str, source: str) -> FuelData:
    return FuelData(
        price=round(price, 2),
        date=date,
        unit="THB/L",
        source=source,
        baseline=BASELINE_DIESEL_PRICE,
        delta_pct=round((price - BASELINE_DIESEL_PRICE) / BASELINE_DIESEL_PRICE, 4),
    )


def _scrape_eppo_live() -> tuple[float, str]:
    """Return (price, date) from the live EPPO HTML. Raises on failure."""
    resp = httpx.get(_EPPO_URL, timeout=FUEL_FETCH_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # TODO: real selectors — the Phase 1 scraper just looks for downloadable
    # links, it doesn't actually parse HTML prices. Live EPPO as of 2026-04 lists
    # Diesel B7 in a table; selectors need to be captured from the live HTML
    # fixture and then translated to a CSS selector. This is a research-after-
    # first-capture activity — see Pitfall 2.
    raise NotImplementedError("scrape selectors: capture live HTML first")


def _read_cached_csv() -> tuple[float, str]:
    df = pd.read_csv(_FUEL_CSV)
    if df.empty:
        raise ValueError("fuel price CSV is empty")
    latest = df.sort_values("date").iloc[-1]
    return float(latest["diesel_b7_price"]), str(latest["date"])
```

### Pattern 5: SQLite rate lookup with half-open tiers (C-02 corrected)

```python
# backend/agent/tools/lookup_rate.py
from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.agent.tools.models import RateResult
from backend.config import DATABASE_PATH


_DB_PATH = Path(DATABASE_PATH)


def lookup_rate(shipping_type: str, zone: str, weight_kg: float) -> RateResult:
    """Look up the base rate in `rate_table` for a shipment.

    Weight-tier match: half-open intervals `[min, max)` per D-13.
    Top tier stored as `weight_max_kg = 999` sentinel (see C-02); weight >= 999
    raises ValueError.

    Args:
        shipping_type: one of "bounce" | "retail_standard" | "retail_fast".
        zone: one of "central-1" | "central-2" | "central-3".
        weight_kg: positive float, up to 998.99kg.

    Returns:
        RateResult(base_rate, currency="THB", rate_tier="5-10kg").

    Raises:
        ValueError: on unknown shipping_type/zone or unmatched weight.
    """
    if weight_kg <= 0:
        raise ValueError(f"weight_kg must be positive, got {weight_kg}")

    query = """
        SELECT base_rate_thb, weight_min_kg, weight_max_kg
        FROM rate_table
        WHERE shipping_type = ?
          AND zone = ?
          AND weight_min_kg <= ?
          AND ? < weight_max_kg
        LIMIT 1
    """
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute(
            query, (shipping_type, zone, weight_kg, weight_kg)
        ).fetchone()

    if row is None:
        raise ValueError(
            f"No rate found for shipping_type={shipping_type!r}, "
            f"zone={zone!r}, weight_kg={weight_kg}"
        )

    base_rate, wmin, wmax = row
    return RateResult(
        base_rate=float(base_rate),
        currency="THB",
        rate_tier=f"{wmin}-{wmax}kg" if wmax < 999 else f"{wmin}+kg",
    )
```

### Pattern 6: In-process TTL cache for routes (D-07)

```python
# backend/agent/tools/_cache.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Generic, Optional, TypeVar

V = TypeVar("V")


@dataclass
class TTLCache(Generic[V]):
    """Minimal in-process TTL cache. Resets on process restart."""
    ttl_seconds: int
    _store: dict = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def get(self, key) -> Optional[V]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, stored_at = entry
            if time.time() - stored_at > self.ttl_seconds:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key, value: V) -> None:
        with self._lock:
            self._store[key] = (value, time.time())

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
```

Use inside `calculate_route.py`:
```python
from backend.agent.tools._cache import TTLCache
from backend.config import ROUTE_CACHE_TTL_SECONDS

_route_cache: TTLCache[RouteData] = TTLCache(ttl_seconds=ROUTE_CACHE_TTL_SECONDS)
```

### Anti-Patterns to Avoid
- **Calling Gemini from tests.** Every test file MUST inject a `FakeMessagesListChatModel` (D-16). Violating this eats the 15 RPM free tier quota and makes CI flaky.
- **Putting tool logic inside node functions.** Tools are in `backend/agent/tools/`, nodes are thin wrappers that call tools. Keeping the split clean lets Phase 3 compose them differently.
- **Catching `Exception` in tools.** Catch only the specific failure modes (httpx.HTTPError, ValueError, sqlite3.Error). The Phase 1 D-11 pattern is: descriptive ValueError, let callers decide. Fuel tool is the exception — its contract is "never raise, always return something" because it has a baseline fallback.
- **Mixing reverse-geocode and directions in one call.** The `googlemaps` client has separate methods. Make two calls and cache both. Tests mock both.
- **Returning raw dicts from tools.** Every tool returns a Pydantic model (TOOL-06). The node serialises via `.model_dump()` when writing to state.
- **Using `datetime.now()` without UTC/timezone.** D-12 trace entries need a deterministic timestamp string. Use `datetime.utcnow().isoformat() + "Z"` (or `datetime.now(timezone.utc).isoformat()` — same effect).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread-safe TTL cache with locking | Custom cache class from scratch | Pattern 6 (tiny TTLCache) is fine. If you find yourself adding more features, switch to `cachetools.TTLCache` | Simple case; upgrade later if needed |
| LLM structured output JSON parsing | Regex + json.loads | `ChatModel.with_structured_output(schema, method="json_schema")` | Model-aware; D-11 retry is a wrapper, not a re-implementation |
| Retry with backoff | `while True: try: ... except: time.sleep(...)` | Pattern 4 inline loop (simple enough) OR `tenacity.retry` decorator | D-04 is only 2 retries — inline is clearer |
| HTTP mocking | Monkeypatch `httpx.get` by hand | `pytest-httpx` fixture | Zero boilerplate, sync+async, minimal test clutter |
| Google Maps response shape | Hand-assembled dicts for testing | Captured real JSON committed to `backend/tests/fixtures/` | One real response file covers Directions + reverse-geocode edge cases |
| SQLite row → Pydantic conversion | Manual dict construction | `conn.row_factory = sqlite3.Row` + `RateResult(**dict(row))` | One-liner, type-safe |
| LangGraph node reducer for `reasoning_trace` append | Manual `state["reasoning_trace"] + [entry]` in every node | `Annotated[List[dict], operator.add]` in AgentState | Idiomatic, atomic under parallel execution (Phase 5 Send API benefits) |
| Zone lookup | Hand-coded province→zone dict in Python | Load `data/raw/zone_definitions.json` at import time into a reverse-index `dict[str, str]` | Single source of truth; already committed in Phase 1 |
| Gemini chat model retries | Custom backoff wrapper | `ChatGoogleGenerativeAI(max_retries=0)` + D-11 single-retry-with-stricter-prompt at the node level | ChatModel built-in retries obscure failure modes; own the retry policy at the narration layer |

**Key insight:** Phase 2 is small in lines of code but dense in integration points. The cheapest bugs here are the ones we prevent by delegating JSON shape, retry policy, HTTP mocking, and SQL parameterisation to well-known libraries. Every hand-rolled solution in Phase 2 is paid for four times (by Phases 3, 4, 5 integration and the final grading review).

## Runtime State Inventory

This phase is additive / greenfield on top of Phase 1's foundation. It does not rename, refactor, or migrate existing code.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `data/express.db` is read-only for Phase 2 tools. No new columns, no new tables. | None |
| Live service config | None — no existing LangGraph or FastAPI runtime. | None |
| OS-registered state | None — no scheduled tasks, no systemd services. | None |
| Secrets / env vars | `.env.example` already contains `GOOGLE_API_KEY`, `GOOGLE_MAPS_API_KEY`. Need to add `GEMINI_MODEL` (default `gemini-2.0-flash`) and a few tuning knobs — see below. | Update `.env.example` and `backend/config.py` |
| Build artifacts | None — no compiled packages; `.venv/` is local-only. | None |

**Config additions to `backend/config.py` and `.env.example`:**
```
# Gemini
GEMINI_MODEL=gemini-2.0-flash

# Phase 2 tuning (D-06, D-07, D-04)
FUEL_FETCH_TIMEOUT=10            # seconds (httpx)
ROUTE_CACHE_TTL_SECONDS=900      # 15 min per architecture.md
TRAFFIC_RATIO_BUCKETS=1.1,1.3,1.5,1.8   # ratio thresholds for severity 2..5
```

## Common Pitfalls

### Pitfall 1: LangGraph default reducer replaces lists
**What goes wrong:** Fuel Agent returns `{"reasoning_trace": [entry]}`; LangGraph merges by REPLACE; the Route Agent's later append overwrites the fuel entry. Result: only the last node's trace survives.
**Why it happens:** `AgentState.reasoning_trace: List[dict]` has no `Annotated[..., reducer]`. LangGraph's merge rule for plain lists is last-write-wins.
**How to avoid:** Update `backend/agent/state.py`:
```python
import operator
from typing_extensions import Annotated

class AgentState(TypedDict):
    ...
    reasoning_trace: Annotated[List[dict], operator.add]  # append across nodes
```
Or, have every node read the prior list and return the full concatenation (shown in Pattern 1). The Annotated reducer is better because it survives parallel execution (future Phase 5 concern).
**Warning signs:** Multi-node tests where earlier trace entries vanish.

### Pitfall 2: EPPO live scrape has no known selectors
**What goes wrong:** The Phase 1 scraper `data/scripts/fetch_fuel_prices.py` only looks for downloadable Excel links — it does NOT actually parse diesel prices from HTML. Phase 2's `fetch_fuel_price` tool needs to parse the current price off the EPPO *page* (or identify a machine-readable endpoint).
**Why it happens:** EPPO has no documented API. The page structure has likely changed since the Phase 1 seed CSV was captured in Oct 2025. Live prices in 2026 are around 30-45 THB/L (varying wildly due to subsidies) — **not the 29.94 baseline**.
**How to avoid:**
1. Capture one live EPPO HTML file as an offline fixture before writing selectors.
2. Write the parser against the fixture (TDD: fixture → failing test → selector → passing test).
3. Treat the live scrape as best-effort — the fallback chain is what makes this robust.
4. If the scrape turns out to be too fragile to develop offline, **downgrade Level 1 to "re-read the CSV seed" and treat Level 2 as the actual primary source for demo purposes.** This is still "real data queried by the agent" per the grading rubric (EPPO data satisfies it), and demo reliability is more valuable than live-fetch cleverness.
**Warning signs:** 403 from EPPO, changed HTML structure, BeautifulSoup returning None for the target selector.

### Pitfall 3: googlemaps client requires `departure_time` for `duration_in_traffic`
**What goes wrong:** You call `gmaps.directions(origin, dest, mode="driving")` and `duration_in_traffic` is missing from the response. Traffic severity falls back to 1.
**Why it happens:** Per Google's API, `duration_in_traffic` only appears when ALL of these are present: `mode="driving"`, `departure_time` (now or future), and no `via:` waypoints. Without `departure_time`, the API returns `duration` only.
**How to avoid:** Always pass `departure_time=datetime.now()` in `calculate_route`. Pass `traffic_model="best_guess"` as well for consistent behaviour. Document this in the tool docstring.
**Warning signs:** Traffic severity is always 1 in live runs even during Bangkok rush hour.

### Pitfall 4: Gemini 2.0 Flash structured-output flakiness
**What goes wrong:** Gemini returns text that doesn't parse to the Pydantic schema. `with_structured_output` raises. Node fails the whole request.
**Why it happens:** Gemini 2.0 Flash is the fastest/cheapest Gemini; structured-output adherence is weaker than 2.5 Pro or 3.x. Free tier rate-limits (15 RPM) can surface as timeouts that look like parse failures.
**How to avoid:** D-11 fallback — retry once with a stricter prompt, then fall back to deterministic narration. Test the deterministic path FIRST (easier to verify) and the LLM path with `FakeMessagesListChatModel` (no real API calls). Set `temperature=0` for reproducibility.
**Warning signs:** Tests fail intermittently; `ValidationError` from Pydantic during Gemini responses.

### Pitfall 5: Timestamp non-determinism in reasoning trace
**What goes wrong:** Tests assert `reasoning_trace[0]["timestamp"] == "2026-04-18T..."` and flake as seconds change.
**Why it happens:** `datetime.utcnow().isoformat()` returns different strings on every call.
**How to avoid:** Either (a) freeze time in tests via `freezegun` or a monkeypatched `datetime.utcnow`, or (b) assert the timestamp field exists + is ISO-8601 but don't pin the exact value. Prefer (b) — less ceremony.
**Warning signs:** Flaky CI.

### Pitfall 6: Zone reverse-lookup case sensitivity
**What goes wrong:** Google Maps returns `administrative_area_level_1.long_name = "Nonthaburi Province"`; `zone_definitions.json` has `"Nonthaburi"` (no "Province" suffix). Zone match returns None.
**Why it happens:** Thai provinces' English names occasionally have "Province" suffix in Google data; occasionally don't. Casing is stable but the suffix isn't.
**How to avoid:** Normalise province names at lookup time: strip `" Province"` suffix, lowercase both sides, then match. Build a reverse-index `dict[str_lower, zone_id]` at import time.
**Warning signs:** Tool raises "No zone found for province X" on real-world requests that clearly map to central-1/2/3.

### Pitfall 7: SQLite connection leak
**What goes wrong:** `lookup_rate` opens a new SQLite connection per call; under load or test parallelism, file handles leak.
**Why it happens:** Forgetting `conn.close()` or `with` block.
**How to avoid:** `with sqlite3.connect(_DB_PATH) as conn:` (shown in Pattern 5). The context manager closes the connection on exit and commits (though we only SELECT).
**Warning signs:** Tests exhaust open files; pytest sporadic "database is locked" errors.

### Pitfall 8: Baseline diverges wildly from live price → cap always hit
**What goes wrong:** `BASELINE_DIESEL_PRICE=29.94` (baseline from Oct 2025). Live EPPO in 2026 shows ~44 THB/L (subsidy-adjusted). Delta is +47%; surcharge formula clamps to the 15% cap. Every live-data answer says "capped".
**Why it happens:** Baseline is a snapshot constant; the world moves.
**How to avoid:** Out of Phase 2 scope to fix (it's a product decision), but **document this in the plan so the demo story is honest**. Options for later: (a) rolling baseline (30-day moving average from the fuel_prices table), (b) quarterly manual update of the env var, (c) accept "capped" answers as realistic. The Fuel Agent's reasoning trace should say "delta is X%, above the cap — recommending 15%" transparently.
**Warning signs:** Every demo query comes back `capped=True` in the result — reviewers ask why.

## Code Examples

Verified patterns from official sources and the Phase 1 codebase.

### Google Maps Directions + Geocoding
```python
# backend/agent/tools/calculate_route.py  (partial)
from __future__ import annotations
from datetime import datetime
import json
from pathlib import Path

import googlemaps

from backend.agent.tools._cache import TTLCache
from backend.agent.tools.models import RouteData
from backend.config import (
    GOOGLE_MAPS_API_KEY,
    ROUTE_CACHE_TTL_SECONDS,
    TRAFFIC_RATIO_BUCKETS,
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ZONE_JSON = _REPO_ROOT / "data" / "raw" / "zone_definitions.json"

_route_cache: TTLCache[RouteData] = TTLCache(ttl_seconds=ROUTE_CACHE_TTL_SECONDS)
_gmaps: googlemaps.Client | None = None  # lazy-init so tests can patch


def _client() -> googlemaps.Client:
    global _gmaps
    if _gmaps is None:
        _gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
    return _gmaps


def _load_zone_index() -> dict[str, str]:
    """Build a case-insensitive province->zone lookup (Pitfall 6)."""
    with open(_ZONE_JSON) as f:
        zones = json.load(f)
    index = {}
    for zone_id, data in zones.items():
        for province in data["provinces"]:
            index[_normalize_province(province)] = zone_id
    return index


def _normalize_province(name: str) -> str:
    name = name.strip()
    if name.lower().endswith(" province"):
        name = name[: -len(" province")]
    return name.lower()


_ZONE_INDEX = _load_zone_index()


def _bucket_traffic(ratio: float) -> int:
    """Map duration_in_traffic/duration ratio to 1-5 severity (D-06)."""
    thresholds = TRAFFIC_RATIO_BUCKETS  # e.g. [1.1, 1.3, 1.5, 1.8]
    for level, threshold in enumerate(thresholds, start=2):
        if ratio < threshold:
            return level - 1  # first bucket below first threshold is 1
    return 5


def calculate_route(origin: str, destination: str) -> RouteData:
    """Fetch route distance/duration/traffic and derive zone."""
    cache_key = (origin, destination)
    if (cached := _route_cache.get(cache_key)) is not None:
        return cached

    client = _client()
    # Directions
    results = client.directions(
        origin,
        destination,
        mode="driving",
        departure_time=datetime.now(),  # required for duration_in_traffic
        traffic_model="best_guess",
    )
    if not results:
        raise ValueError(f"No route from {origin!r} to {destination!r}")

    leg = results[0]["legs"][0]
    distance_km = leg["distance"]["value"] / 1000.0
    duration_min = leg["duration"]["value"] // 60
    duration_s = leg["duration"]["value"]
    duration_traffic_s = leg.get("duration_in_traffic", {}).get("value", duration_s)
    severity = _bucket_traffic(duration_traffic_s / duration_s)

    # Reverse geocode destination
    zone = _zone_for_destination(destination)

    route = RouteData(
        origin=origin,
        destination=destination,
        distance_km=round(distance_km, 2),
        duration_min=int(duration_min),
        traffic_severity=severity,
        zone=zone,
    )
    _route_cache.set(cache_key, route)
    return route


def _zone_for_destination(destination: str) -> str:
    components = _client().geocode(destination)
    if not components:
        raise ValueError(f"Could not geocode destination {destination!r}")
    for comp in components[0]["address_components"]:
        if "administrative_area_level_1" in comp["types"]:
            norm = _normalize_province(comp["long_name"])
            if norm in _ZONE_INDEX:
                return _ZONE_INDEX[norm]
    raise ValueError(f"No Central Region zone for {destination!r}")
```
**Source:** Google Maps Directions API spec (duration_in_traffic when departure_time + driving mode). `googlemaps.Client.directions()` signature: https://github.com/googlemaps/google-maps-services-python/blob/master/googlemaps/directions.py

### Testing with `FakeMessagesListChatModel`
```python
# backend/tests/test_fuel_agent.py (partial)
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from backend.agent.nodes import fuel_agent as fuel_agent_module


def test_fuel_agent_emits_trace_entry_with_deterministic_fallback(monkeypatch, mocker):
    # 1. Mock the tool to return a known FuelData.
    fake_fuel = FuelData(
        price=31.00, date="2026-04-18", unit="THB/L",
        source="eppo_live", baseline=29.94, delta_pct=0.0354,
    )
    mocker.patch.object(
        fuel_agent_module, "fetch_fuel_price", return_value=fake_fuel,
    )

    # 2. Replace the Gemini factory with a FakeMessagesListChatModel that
    #    returns a JSON AIMessage matching the FuelReasoning schema.
    scripted = FakeMessagesListChatModel(responses=[
        AIMessage(content='{"summary": "Diesel 3.5% above baseline.", "trend": "above_baseline"}')
    ])
    monkeypatch.setattr(fuel_agent_module, "get_chat_model", lambda **_: scripted)

    # 3. Run the node.
    state = {
        "messages": [], "fuel_data": None, "route_data": None,
        "shipping_type": "bounce", "weight_kg": 10.0,
        "surcharge_result": None, "reasoning_trace": [], "next_step": "",
    }
    result = fuel_agent_module.fuel_agent_node(state)

    # 4. Assertions.
    assert result["fuel_data"]["price"] == 31.00
    assert result["fuel_data"]["source"] == "eppo_live"
    trace = result["reasoning_trace"][-1]
    assert trace["agent"] == "fuel_agent"
    assert trace["tool"] == "fetch_fuel_price"
    assert trace["status"] == "ok"
    assert "above_baseline" in trace["reasoning"]
```
**Source:** `FakeMessagesListChatModel` — `responses: list[BaseMessage]`, cycles in order. https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/language_models/fake_chat_models.py

### Testing with `pytest-httpx`
```python
# backend/tests/test_fetch_fuel_price.py
import httpx
import pytest

from backend.agent.tools.fetch_fuel_price import fetch_fuel_price


def test_fuel_tool_falls_back_to_cached_csv_when_eppo_is_down(httpx_mock):
    # All 3 live attempts fail with network error.
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))

    result = fetch_fuel_price()
    assert result.source == "eppo_cached_csv"
    assert result.price > 0


def test_fuel_tool_falls_back_to_baseline_when_csv_is_missing(
    httpx_mock, monkeypatch, tmp_path
):
    from backend.agent.tools import fetch_fuel_price as mod
    for _ in range(3):
        httpx_mock.add_exception(httpx.ConnectError("boom"))
    # Point the module's CSV path to a nonexistent file.
    monkeypatch.setattr(mod, "_FUEL_CSV", tmp_path / "missing.csv")

    result = fetch_fuel_price()
    assert result.source == "hardcoded_baseline"
    assert result.price == pytest.approx(29.94)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests` + `responses` for HTTP mocking | `httpx` + `pytest-httpx` / `respx` | 2023+ (httpx became async default) | Phase 2 D-02 picks httpx; C-01 corrects the test library |
| LangChain `initialize_agent()` ReAct | LangGraph `StateGraph` with explicit nodes | 2024 | Already Phase 1's choice; Phase 2 builds nodes not ReAct loops |
| Gemini tool calling via hand-parsed JSON | `ChatGoogleGenerativeAI.bind_tools()` + `with_structured_output()` | 2024 (langchain-google-genai 2.x) | Phase 2 D-09/D-11 use the modern path |
| Pydantic v1 `validator` | v2 `field_validator`, `model_validator` | 2023 (v2 release) | Phase 1 already on v2 — continue |
| `FakeListChatModel` (strings) | `FakeMessagesListChatModel` (AIMessages with tool_calls) | 2024 | Necessary for testing tool-calling agents — strings alone can't carry tool_calls |

**Deprecated/outdated:**
- `google-generativeai` SDK direct use for LangGraph agents — use `langchain-google-genai` wrapper.
- `responses` library for httpx — does not work (C-01).
- `gemini-pro` / `gemini-1.5-flash` model names — superseded by `gemini-2.0-flash` (which is what CLAUDE.md targets).

## Open Questions

1. **Whether to change `AgentState.reasoning_trace` to `Annotated[List[dict], operator.add]`**
   - What we know: Phase 1's `state.py` has plain `List[dict]`. LangGraph's default merge is replace, not append.
   - What's unclear: Whether "change a Phase 1 artifact" is acceptable or whether we must work around it in Phase 2.
   - Recommendation: Make the change. Document it as a Wave 0 task in Phase 2 (editing `backend/agent/state.py` to add the `Annotated` import and reducer). It's 3 lines of code, backward-compatible for the tests that use plain lists, and prevents Pitfall 1 permanently.

2. **Whether to actually attempt the live EPPO scrape in Phase 2**
   - What we know: Phase 1's scraper is a no-op (looks for downloadable links; doesn't parse prices). No selectors are known.
   - What's unclear: Whether to invest time in selectors now or defer to "CSV is the primary source" for demo.
   - Recommendation: Implement the tool with the 3-level chain plumbing, but stub `_scrape_eppo_live` to raise `NotImplementedError` initially — the fallback chain kicks in, tests pass, and we've preserved the seam for later. Capture real EPPO HTML as a fixture when time permits; fill in selectors in a follow-up task or Phase 5 polish.

3. **Whether the Fuel Agent's system prompt should advertise `search_fuel_news`**
   - What we know: D-09 mentions Gemini sees both `fetch_fuel_price` and `search_fuel_news` as available tools, but TOOL-05 is Phase 5.
   - What's unclear: Phase 2 grading may benefit from "agent reasons about optional web search" even if the tool isn't connected.
   - Recommendation: Don't advertise a tool that doesn't exist — Gemini will hallucinate tool calls and the node will fail. Keep the Phase 2 system prompt to `fetch_fuel_price` only; add `search_fuel_news` to the prompt in Phase 5 when the tool lands.

4. **Whether tool-level (D-04) retry remains once the Phase 3 agentic wrapper (ORCH-08) is in place**
   - What we know: D-04 says in-tool retries are a "local stand-in". ORCH-08 is Phase 3.
   - What's unclear: Whether to remove D-04 retries in Phase 3 or leave them as defence in depth.
   - Recommendation: Leave them. "In-tool" retries protect against transient network blips cheaply; "in-agent" retries protect against semantic failures (wrong tool call). They compose.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.9+ interpreter | All code | ✓ | 3.9.6 (system CLT) | — |
| `.venv` virtualenv | All code | ✓ | `.venv/bin/python3.9` | — |
| pip | Install new deps | ✓ | built-in | — |
| SQLite | `lookup_rate` | ✓ | 3.x (stdlib) | — |
| SQLite seeded DB | `lookup_rate` | ✓ | `data/express.db` 27KB, 45 rate rows | — |
| zone JSON | route zone derivation | ✓ | `data/raw/zone_definitions.json` | — |
| EPPO seed CSV | fuel fallback Level 2 | ✓ | `data/raw/eppo_diesel_prices.csv` 185 rows | — |
| Google Maps API key | TOOL-02 live calls | ✗ (env-only) | — | Mocked in tests; live requires operator to add `GOOGLE_MAPS_API_KEY` to `.env` |
| Gemini API key | ORCH-02/03 live calls | ✗ (env-only) | — | Mocked in tests via FakeMessagesListChatModel; live requires `GOOGLE_API_KEY` |
| Internet | EPPO scrape Level 1 | — | — | Level 2 (CSV) → Level 3 (baseline) fallback |
| Python 3.11+ | CLAUDE.md nominal spec | ✗ | — | **Not blocking** — 3.9.6 works with `from __future__ import annotations` pattern (C-03) |

**Missing dependencies with no fallback:** None. Every runtime dependency has a test-time mock or a real fallback.

**Missing dependencies with fallback:**
- Google Maps / Gemini API keys at test time — fully mocked, no action needed
- Live internet at runtime — fuel tool falls back gracefully; route tool requires Google Maps reachable for live demo (acceptable)

**Action items surfaced for the planner:**
- Add `Wave 0` task: install the 7 new dependencies, regenerate `requirements.txt`.
- Add `Wave 0` task: update `backend/agent/state.py` for Pitfall 1 (the `Annotated[..., operator.add]` reducer for `reasoning_trace`).
- Add `Wave 0` task: expand `FuelData.source` field commentary per D-03 (no type change — `source: str` already; just document the new values).
- Add `Wave 0` task: add `GEMINI_MODEL`, `FUEL_FETCH_TIMEOUT`, `ROUTE_CACHE_TTL_SECONDS`, `TRAFFIC_RATIO_BUCKETS` to `backend/config.py` and `.env.example`.
- Capture live EPPO HTML and one Google Maps Directions + Geocoding JSON pair as committed fixtures (separate task, can be done as Wave 0 or in parallel with code tasks).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` 8.4.2 |
| Config file | None — Phase 1 Wave 0 gap not yet filled; recommend adding `pyproject.toml` `[tool.pytest.ini_options]` in Phase 2 Wave 0 |
| Quick run command | `.venv/bin/python -m pytest backend/tests/ -x -q` |
| Full suite command | `.venv/bin/python -m pytest backend/tests/ -v` |
| Current passing | 35/35 tests (Phase 1 green) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | `fetch_fuel_price` live-level happy path returns FuelData with source=`eppo_live` | unit | `python -m pytest backend/tests/test_fetch_fuel_price.py::test_live_happy_path -x` | ❌ Wave 0 |
| TOOL-01 | Falls back to cached CSV after 3 failed live attempts; source=`eppo_cached_csv` | unit | `python -m pytest backend/tests/test_fetch_fuel_price.py::test_falls_back_to_csv -x` | ❌ Wave 0 |
| TOOL-01 | Falls back to `BASELINE_DIESEL_PRICE` when CSV missing; source=`hardcoded_baseline` | unit | `python -m pytest backend/tests/test_fetch_fuel_price.py::test_falls_back_to_baseline -x` | ❌ Wave 0 |
| TOOL-01 | Retry honours 1s / 2s exponential backoff (D-04) | unit | `python -m pytest backend/tests/test_fetch_fuel_price.py::test_retry_backoff -x` | ❌ Wave 0 |
| TOOL-02 | Returns RouteData with correct distance/duration from mocked directions response | unit | `python -m pytest backend/tests/test_calculate_route.py::test_directions_parsing -x` | ❌ Wave 0 |
| TOOL-02 | Traffic ratio 1.2 maps to severity 2; 1.9 maps to 5 (D-06) | unit | `python -m pytest backend/tests/test_calculate_route.py::test_traffic_bucketing -x` | ❌ Wave 0 |
| TOOL-02 | Reverse-geocoded Bangkok → `central-1`, Ayutthaya → `central-2`, Lop Buri → `central-3` | unit | `python -m pytest backend/tests/test_calculate_route.py::test_zone_derivation -x` | ❌ Wave 0 |
| TOOL-02 | Cache hit on repeat call within TTL; cache miss after TTL expiry | unit | `python -m pytest backend/tests/test_calculate_route.py::test_cache_ttl -x` | ❌ Wave 0 |
| TOOL-02 | Missing API key / no routes raises ValueError | unit | `python -m pytest backend/tests/test_calculate_route.py::test_no_routes_raises -x` | ❌ Wave 0 |
| TOOL-02 | Province suffix normalization (Pitfall 6) | unit | `python -m pytest backend/tests/test_calculate_route.py::test_province_suffix_normalization -x` | ❌ Wave 0 |
| TOOL-03 | Known shipping_type+zone+weight returns correct base rate | unit | `python -m pytest backend/tests/test_lookup_rate.py::test_known_tier -x` | ❌ Wave 0 |
| TOOL-03 | Half-open interval: 5.0 kg goes to 5-10 tier, not 0-5 (D-13) | unit | `python -m pytest backend/tests/test_lookup_rate.py::test_half_open_boundary -x` | ❌ Wave 0 |
| TOOL-03 | Unknown shipping_type raises ValueError (D-14) | unit | `python -m pytest backend/tests/test_lookup_rate.py::test_unknown_shipping_type -x` | ❌ Wave 0 |
| TOOL-03 | Unknown zone raises ValueError (D-14) | unit | `python -m pytest backend/tests/test_lookup_rate.py::test_unknown_zone -x` | ❌ Wave 0 |
| TOOL-03 | Weight above top tier raises ValueError | unit | `python -m pytest backend/tests/test_lookup_rate.py::test_weight_too_heavy -x` | ❌ Wave 0 |
| TOOL-03 | Negative/zero weight raises ValueError | unit | `python -m pytest backend/tests/test_lookup_rate.py::test_invalid_weight -x` | ❌ Wave 0 |
| TOOL-04 | `@tool` wrapper returns same SurchargeResult as pure function for representative input | unit | `python -m pytest backend/tests/test_calculate_surcharge_tool.py::test_wrapper_parity -x` | ❌ Wave 0 |
| TOOL-04 | `.invoke({...})` with dict input works and validates via SurchargeInput schema | unit | `python -m pytest backend/tests/test_calculate_surcharge_tool.py::test_invoke_dict -x` | ❌ Wave 0 |
| ORCH-02 | Fuel Agent node called with sample AgentState updates `fuel_data` and appends one trace entry | unit | `python -m pytest backend/tests/test_fuel_agent.py::test_state_updates -x` | ❌ Wave 0 |
| ORCH-02 | D-11 fallback: Gemini raises → node emits deterministic trace entry, still ok | unit | `python -m pytest backend/tests/test_fuel_agent.py::test_gemini_failure_fallback -x` | ❌ Wave 0 |
| ORCH-02 | Trace entry matches D-12 schema (step, agent, tool, tool_input, tool_output, reasoning, timestamp, status) | unit | `python -m pytest backend/tests/test_fuel_agent.py::test_trace_schema -x` | ❌ Wave 0 |
| ORCH-03 | Route Agent node updates `route_data` and appends trace entry | unit | `python -m pytest backend/tests/test_route_agent.py::test_state_updates -x` | ❌ Wave 0 |
| ORCH-03 | Route Agent propagates zone into trace and RouteData | unit | `python -m pytest backend/tests/test_route_agent.py::test_zone_in_output -x` | ❌ Wave 0 |
| ORCH-03 | Trace entry matches D-12 schema | unit | `python -m pytest backend/tests/test_route_agent.py::test_trace_schema -x` | ❌ Wave 0 |
| Regression | Phase 1 tests still green after `AgentState` reducer change | smoke | `python -m pytest backend/tests/test_models.py backend/tests/test_surcharge.py -v` | ✅ exists (Phase 1) |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest backend/tests/ -x -q` (expect < 10 seconds for the whole suite even with Phase 2 additions)
- **Per wave merge:** `.venv/bin/python -m pytest backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`. Target: 35 existing + ~25 new = ~60 passing tests.

### Wave 0 Gaps
- [ ] `backend/tests/conftest.py` — shared fixtures: `sample_agent_state`, `mocked_gmaps_client`, `seeded_sqlite`, `fake_gemini_model`, `eppo_html_fixture`
- [ ] `backend/tests/fixtures/eppo_sample.html` — captured HTML for offline tests
- [ ] `backend/tests/fixtures/gmaps_directions.json` — captured Directions response
- [ ] `backend/tests/fixtures/gmaps_geocode_bangkok.json` — captured Geocoding response
- [ ] `backend/tests/fixtures/gmaps_geocode_ayutthaya.json` — central-2 example
- [ ] `backend/tests/fixtures/gmaps_geocode_lopburi.json` — central-3 example
- [ ] `backend/tests/test_fetch_fuel_price.py` — TOOL-01 (4-6 tests)
- [ ] `backend/tests/test_calculate_route.py` — TOOL-02 (6-8 tests)
- [ ] `backend/tests/test_lookup_rate.py` — TOOL-03 (6 tests)
- [ ] `backend/tests/test_calculate_surcharge_tool.py` — TOOL-04 (2-3 tests)
- [ ] `backend/tests/test_fuel_agent.py` — ORCH-02 (3-4 tests)
- [ ] `backend/tests/test_route_agent.py` — ORCH-03 (3-4 tests)
- [ ] `pyproject.toml` — `[tool.pytest.ini_options]` with `testpaths = ["backend/tests"]`, `addopts = "-ra -q"`, and `filterwarnings` entries for known deprecations
- [ ] `requirements.txt` — add langgraph, langchain-core, langchain-google-genai, googlemaps, httpx, pytest-httpx, pytest-mock
- [ ] `backend/agent/state.py` — add `Annotated[List[dict], operator.add]` for `reasoning_trace` (Pitfall 1)
- [ ] `backend/config.py` — add `GOOGLE_MAPS_API_KEY`, `GOOGLE_API_KEY`, `GEMINI_MODEL`, `FUEL_FETCH_TIMEOUT`, `ROUTE_CACHE_TTL_SECONDS`, `TRAFFIC_RATIO_BUCKETS`
- [ ] `.env.example` — add `GEMINI_MODEL=gemini-2.0-flash` and tuning knobs

## Sources

### Primary (HIGH confidence)
- Phase 1 artifacts (verified via Read tool): `backend/agent/state.py`, `backend/agent/tools/models.py`, `backend/agent/tools/calculate_surcharge.py`, `backend/config.py`, `data/raw/zone_definitions.json`, `data/scripts/seed_database.py`, `data/scripts/fetch_fuel_prices.py`, `.planning/phases/01-foundation-data-pipeline/01-RESEARCH.md`
- `.planning/phases/02-tools-agent-nodes/02-CONTEXT.md` — locked decisions
- CLAUDE.md — project conventions and constraints
- [LangGraph use-graph-api documentation](https://docs.langchain.com/oss/python/langgraph/use-graph-api) — node signature `State -> Partial<State>`, reducers for `Annotated` list fields
- [ChatGoogleGenerativeAI documentation](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai) — `bind_tools()`, `with_structured_output(schema, method="json_schema")`
- [googlemaps Python client directions source](https://github.com/googlemaps/google-maps-services-python/blob/master/googlemaps/directions.py) — `directions()` function signature verified
- [LangChain fake_chat_models source](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/language_models/fake_chat_models.py) — `FakeMessagesListChatModel.responses: list[BaseMessage]`
- `pip index versions` output on 2026-04-18 — all package versions verified

### Secondary (MEDIUM confidence)
- [Google Maps Directions API response schema](https://developers.google.com/maps/documentation/directions/get-directions) — duration/distance JSON shape, duration_in_traffic availability rules
- [pytest-httpx documentation](https://colin-b.github.io/pytest_httpx/) — fixture usage pattern for httpx mocking
- [EPPO Petroleum Price Statistic page](https://www.eppo.go.th/index.php/en/en-energystatistics/petroleumprice-statistic) — confirmed accessible; selectors unverified (Pitfall 2)

### Tertiary (LOW confidence)
- EPPO live HTML structure in April 2026 — only one capture needed at implementation time; seed CSV mitigates entirely
- Gemini 2.0 Flash rate-limit behaviour under structured output — based on general LangChain community reports; D-11 fallback handles any failure mode

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified via `pip index versions`; ecosystem maturity (LangGraph 0.6, langchain-google-genai 2.1.x, googlemaps 4.10) is stable
- Architecture (nodes / tools / cache): HIGH — patterns directly from LangGraph/LangChain current docs and Phase 1 code
- Pitfalls: HIGH for 1, 3-7 (concrete; code verified); MEDIUM for 2 (EPPO selectors unverified); MEDIUM for 8 (baseline drift — real concern but not a code bug)
- Corrections (C-01, C-02, C-03): HIGH — all three are empirical findings (venv version, DB SELECT, library compat)
- Testing mock libraries: HIGH — pytest-httpx + FakeMessagesListChatModel both verified against source/docs

**Research date:** 2026-04-18
**Valid until:** 2026-05-18 (30 days — stable domain: LangGraph, LangChain, googlemaps, httpx all unlikely to break the described patterns; Gemini 2.0 Flash may be superseded by 2.5 Flash on Google's side but `GEMINI_MODEL` is env-configurable so the swap is one-env-var cheap)
