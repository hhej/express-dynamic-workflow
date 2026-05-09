---
phase: quick-260509-uwb
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/nodes/pricing_agent.py
  - backend/agent/prompts/pricing_agent.py
  - backend/tests/test_pricing_agent.py
autonomous: true
requirements:
  - QUICK-260509-UWB-01  # Visible multi-step pricing reasoning bullets in trace
  - QUICK-260509-UWB-02  # Volatility-window signal derived from existing CSV (no new APIs)
  - QUICK-260509-UWB-03  # search_context relevance bullet wired from existing state field

must_haves:
  truths:
    - "Pricing Agent narration emits 3-5 bullet steps (base rate, fuel delta + volatility, traffic, search context if present, final %/total)"
    - "Trace entry's `reasoning` field is a multi-line string with `- ` bullets that render verbatim in the existing TraceStep UI"
    - "Deterministic surcharge formula in calculate_surcharge.py is byte-for-byte unchanged; existing formula and D-11 fallback tests pass without modification"
    - "Volatility flag (low/normal/high) is computed from data/raw/eppo_diesel_prices.csv (last 7 days vs current) — no new external API call"
    - "When state.search_context is present, the news bullet appears; when absent, the news bullet is omitted (not rendered as 'no data')"
    - "When the LLM call or JSON parse fails, the deterministic fallback produces the SAME bullet structure (not a degraded one-liner)"
  artifacts:
    - path: "backend/agent/nodes/pricing_agent.py"
      provides: "Pricing agent node with bullet narration + volatility helper + search_context wiring"
      contains: "_compute_volatility_flag"
    - path: "backend/agent/prompts/pricing_agent.py"
      provides: "Updated SYSTEM_PROMPT instructing LLM to emit {summary, bullets} given augmented context"
      contains: "bullets"
    - path: "backend/tests/test_pricing_agent.py"
      provides: "Test coverage for bullet emission, volatility flag, search_context wiring, and bullet-shaped fallback"
      contains: "test_emits_bullet_reasoning"
  key_links:
    - from: "backend/agent/nodes/pricing_agent.py::pricing_agent_node"
      to: "data/raw/eppo_diesel_prices.csv"
      via: "_compute_volatility_flag(history_csv_path, current_price)"
      pattern: "_compute_volatility_flag"
    - from: "backend/agent/nodes/pricing_agent.py::pricing_agent_node"
      to: "state['search_context']"
      via: "state.get('search_context') read inside narration builder"
      pattern: "search_context"
    - from: "backend/agent/nodes/pricing_agent.py::pricing_agent_node"
      to: "trace_entry['reasoning']"
      via: "newline-joined '- bullet' string"
      pattern: "reasoning.*\\\\n.*-"
    - from: "backend/agent/prompts/pricing_agent.py::SYSTEM_PROMPT"
      to: "PricingReasoning schema"
      via: "JSON contract: {summary: str, bullets: list[str]}"
      pattern: "bullets"
---

<objective>
Upgrade the Pricing Agent so its reasoning is **visibly multi-step** in the user-facing trace. The agent already runs a deterministic surcharge calculation (formula in `backend/agent/tools/calculate_surcharge.py`) — that formula is locked. What changes is the *narration*: replace the current 1-sentence summary with 3-5 short bullets that walk the user through base rate, fuel delta + 7-day volatility flag, traffic severity factor (when relevant), search-context relevance (when state has it), and the final surcharge percent + total (with cap/floor note).

Purpose: This is the "agentic feel" upgrade. The product's core value is *transparently reasoning* over fuel/route/shipping data; the formula being deterministic doesn't preclude the agent from explaining each input it weighed. Per CONTEXT.md D-01..D-04, the formula is unchanged, the schema gains `bullets: list[str]`, signals come from existing state + the existing EPPO CSV (no new API calls, stays under the 15 RPM Gemini ceiling).

Output:
- `backend/agent/nodes/pricing_agent.py` updated with a volatility helper, an augmented LLM prompt context, a bullet-shaped deterministic fallback, and trace `reasoning` formatted as newline-joined `- bullet` markdown.
- `backend/agent/prompts/pricing_agent.py` updated SYSTEM_PROMPT instructing Gemini to emit `{summary, bullets}` with explicit bullet-construction rules (one signal per bullet, no invented numbers).
- `backend/tests/test_pricing_agent.py` extended with 4 new tests covering bullet emission, volatility flag categories, search_context-present-vs-absent rendering, and bullet-shaped deterministic fallback. All 4 existing pricing tests must pass unchanged.
</objective>

<execution_context>
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/workflows/execute-plan.md
@/Users/pollot/Desktop/express-dynamic-workflow/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260509-uwb-upgrade-pricing-agent-to-visibly-reason-/260509-uwb-CONTEXT.md

# Primary edit targets (read fully before editing)
@backend/agent/nodes/pricing_agent.py
@backend/agent/prompts/pricing_agent.py
@backend/tests/test_pricing_agent.py

# Read-only references (DO NOT MODIFY — formula and schemas are locked contracts)
@backend/agent/tools/calculate_surcharge.py
@backend/agent/tools/models.py
@backend/agent/state.py
@backend/agent/llm.py

# UI sink (informational — confirms `reasoning` string renders as-is)
@frontend/components/trace/TraceStep.tsx

# Volatility data source (495 rows, monthly cadence pre-2026, daily 2026+)
# Latest rows confirmed: 2026-04-30 40.20, 2026-05-01..05-07 40.80, 2026-05-08 39.95, 2026-05-09 39.95
@data/raw/eppo_diesel_prices.csv

<interfaces>
<!-- Key contracts the executor needs. Extracted from codebase. -->
<!-- Use these directly — no codebase exploration needed. -->

From backend/agent/tools/models.py (LOCKED — do NOT modify):
```python
class SurchargeResult(BaseModel):
    surcharge_pct: float    # e.g., 0.05 = 5%
    surcharge_amount: float # THB
    total: float            # THB
    capped: bool

class RateResult(BaseModel):
    base_rate: float        # THB
    currency: str = "THB"
    rate_tier: str          # e.g., "11-25kg"

class FuelData(BaseModel):
    price: float
    date: str               # YYYY-MM-DD
    baseline: float
    delta_pct: float
    source: str
    unit: str = "THB/L"

class SearchResult(BaseModel):  # = state["search_context"] shape
    query: str
    summary: Optional[str]   # 1-line LLM answer from Tavily
    sources: List[SearchSource]
    fetched_at: str
```

From backend/agent/state.py (search_context field present since Phase 5):
```python
search_context: Optional[dict]
# Shape matches SearchResult.model_dump(); None when no news/market query was routed.
```

From backend/agent/nodes/pricing_agent.py (current schema — to be EXTENDED):
```python
class PricingReasoning(BaseModel):
    summary: str  # Existing — KEEP for backward compat per D-04
    # ADD: bullets: list[str] = Field(default_factory=list)
```

From backend/agent/tools/calculate_surcharge.py (READ-ONLY — formula contract):
```python
# 1. fuel_delta_pct = (current - BASELINE_DIESEL_PRICE) / BASELINE_DIESEL_PRICE
# 2. surcharge_pct = fuel_delta_pct * SHIPPING_MULTIPLIERS[shipping_type]
# 3. If bounce: surcharge_pct += traffic_severity * 0.02
# 4. Clamp to [SURCHARGE_FLOOR, SURCHARGE_CAP]; capped flag set if either boundary hit
# 5. amounts rounded; total = base + amount
```

From frontend/components/trace/TraceStep.tsx:
```tsx
// entry.reasoning rendered as <span className="truncate ...">{entry.reasoning}</span>
// Collapsed: single truncated line. Expanded panel shows tool input/output JSON.
// Newline-joined "- bullet" markdown will appear inline (single line collapsed,
// readable when the user expands a step). No frontend change needed (per CONTEXT.md scope).
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add bullets field + volatility helper + bullet narration in pricing_agent.py</name>
  <files>backend/agent/nodes/pricing_agent.py</files>
  <behavior>
    Tests will assert (these belong in Task 3 — same plan, listed here so the executor sees the full contract while writing the implementation):
    - PricingReasoning now has a `bullets: list[str]` field (defaults to empty list) alongside the existing `summary: str`.
    - `_compute_volatility_flag(history_csv_path: pathlib.Path, current_price: float) -> Literal["low","normal","high"]` exists and is pure (CSV read only). Categorization rule:
        * Read last 7 dated rows (skip today's row if it equals current_price; use the most-recent 7 distinct calendar days available).
        * Compute `mean_abs_delta = mean(|price[i] - price[i-1]|)` over the window.
        * Compute `recent_delta = abs(current_price - last_window_price)` (last_window_price = first row of the 7-day window, i.e., 7 days ago).
        * Threshold:
            - `recent_delta > 0.5 * mean_abs_delta` AND `mean_abs_delta > 0` → `"high"`
            - `recent_delta < 0.2 * mean_abs_delta` → `"low"`
            - otherwise → `"normal"`
        * If fewer than 2 rows available OR mean_abs_delta == 0 → return `"normal"` (safe default; never raise).
    - The trace entry's `reasoning` field is a multi-line string starting with `- ` on each non-empty line (newline-joined bullet markdown).
    - Bullet count is between 3 and 5 inclusive in the happy path.
    - When `state["search_context"]` is None or missing → no news bullet is emitted (bullet count drops to 3-4).
    - When `state["search_context"]` is a dict with a non-empty `summary` → a news bullet is emitted that includes the summary text (or a truncated form ≤120 chars).
    - When the LLM raises or emits invalid JSON → deterministic fallback emits the SAME bullet shape (3-5 bullets, newline-joined `- `), NOT the old single-sentence string. Trace `status` stays `"ok"` per D-11 contract.
    - Bullet 1 always references the rate tier and base rate; bullet 2 always references fuel delta_pct (or the difference vs baseline) AND the volatility flag word; the final bullet always references the final surcharge_pct and total, with `(capped)` or `(floor applied)` text when `surcharge.capped is True`.
    - The traffic-severity bullet is emitted ONLY when `shipping_type == "bounce"` (mirrors the formula's traffic adjustment rule); for retail_standard / retail_fast it is omitted.
    - Existing 4 tests (test_computes_surcharge_and_emits_trace, test_bubbles_value_error_from_lookup_rate, test_gemini_failure_deterministic_fallback, test_guards_missing_route_data, test_guards_missing_fuel_data) continue to pass without edits — they only assert structure and a numeric reference, both still hold.
  </behavior>
  <action>
    1. **Extend PricingReasoning schema** (top of file, replace existing class):
       ```python
       class PricingReasoning(BaseModel):
           """Structured narration schema for the Pricing Agent (D-11).

           D-04 (CONTEXT 260509-uwb): kept `summary` for backward compat; added
           `bullets` for multi-step reasoning that surfaces in the trace UI.
           """
           summary: str = Field(description="One-sentence pricing summary")
           bullets: list[str] = Field(
               default_factory=list,
               description="3-5 short reasoning steps walking the user through "
                           "base rate, fuel delta + volatility, traffic, news context, "
                           "and final surcharge.",
           )
       ```

    2. **Add `_compute_volatility_flag` helper** (near top of file, after imports, before PricingReasoning). Per the behavior block above. Use `pathlib.Path`, `csv.DictReader`. Default `history_csv_path` to `Path(__file__).resolve().parents[3] / "data" / "raw" / "eppo_diesel_prices.csv"` so production calls work without a path arg, but tests can inject a tmp_path CSV. Wrap CSV read in try/except returning `"normal"` on any IO/parse error (silent — file missing must NOT crash the pricing agent).

    3. **Add `_build_bullets(rate, surcharge, fuel_data, route_data, shipping_type, volatility_flag, search_context) -> list[str]` helper.** This is the deterministic bullet builder used both as the fallback narration AND as the seed/reference handed to the LLM. Bullet templates (use `_` for unused values):
       - Bullet 1 (always): `f"Base rate {rate.base_rate:.2f} THB ({rate.rate_tier} tier, zone {route_data['zone']}, {shipping_type})."`
       - Bullet 2 (always): `f"Diesel at {fuel_data['price']:.2f} THB/L vs baseline {fuel_data['baseline']:.2f} ({fuel_data['delta_pct']:+.2%} delta, volatility {volatility_flag} over last 7 days)."`
       - Bullet 3 (bounce only): `f"Bangkok Metro traffic severity {route_data['traffic_severity']}/5 adds a per-step bump on top of the fuel delta."`
       - Bullet 4 (only if search_context present and has non-empty summary): `f"Market context: {summary[:120]}{'...' if len(summary) > 120 else ''}"` (summary read from `search_context.get('summary')`).
       - Bullet 5 (always, last): `f"Final surcharge {surcharge.surcharge_pct:.2%} = {surcharge.surcharge_amount:.2f} THB; total {surcharge.total:.2f} THB{cap_note}."` where `cap_note = " (cap applied)" if surcharge.capped and surcharge.surcharge_pct >= 0 else " (floor applied)" if surcharge.capped else ""`.

       Compose into a list, filtering out the bounce-only and search-context-only bullets when their predicates are false. Final list length will be 3, 4, or 5.

    4. **Replace `_deterministic_narration`** to delegate to `_build_bullets` and join with newlines:
       ```python
       def _deterministic_narration(...) -> str:
           bullets = _build_bullets(...)
           return "\n".join(f"- {b}" for b in bullets)
       ```
       Update its signature to take all the new args (rate, surcharge, fuel_data, route_data, shipping_type, volatility_flag, search_context).

    5. **Replace `_narrate_with_llm`** to: (a) build the bullet seed via `_build_bullets`, (b) pass that seed into the prompt as the user-message JSON payload, (c) parse `{summary, bullets}`, (d) on any failure return the deterministic newline-joined bullets (NOT a single sentence). When LLM succeeds AND its `bullets` list is non-empty AND has 3-5 items, prefer the LLM's bullets; otherwise fall back to the deterministic ones. Always return the joined `"- bullet\n- bullet\n..."` string.

    6. **Wire into `pricing_agent_node`** between the surcharge calculation and the trace_entry build:
       - Compute `volatility_flag = _compute_volatility_flag(DEFAULT_CSV, current_diesel_price)`.
       - Read `search_context = state.get("search_context")`.
       - Call `reasoning = _narrate_with_llm(rate, surcharge, fuel_data, route_data, shipping_type, volatility_flag, search_context)`.
       - Trace entry shape, status="ok", and OBS-03 auto-eval block all unchanged. Do NOT add new state writes.

    7. **DO NOT** touch:
       - `backend/agent/tools/calculate_surcharge.py` (formula)
       - `backend/agent/tools/calculate_surcharge_tool.py` (tool wrapper)
       - `backend/agent/tools/models.py` (SurchargeResult / SurchargeInput / SearchResult)
       - `AgentState` definition (state.py)
       - The graph wiring in `backend/agent/graph.py`
       - The OBS-03 auto-eval call (lines ~227-240 in current file) — preserved verbatim

    Implement per CONTEXT.md D-01 (formula unchanged), D-02 (multi-step bullets), D-03 (existing state only — no new APIs).
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && .venv/bin/python -m pytest backend/tests/test_pricing_agent.py -x -q</automated>
  </verify>
  <done>
    - `PricingReasoning` has both `summary: str` and `bullets: list[str]` fields.
    - `_compute_volatility_flag` exists, returns one of `"low"|"normal"|"high"`, never raises.
    - `_build_bullets` produces 3-5 bullets per the templates above.
    - `_deterministic_narration` returns a `"- ..."` newline-joined string (NOT a single sentence).
    - `_narrate_with_llm` produces a newline-joined `- bullet` string in both LLM-success and LLM-failure paths.
    - `pricing_agent_node` wires volatility + search_context into the narration call site.
    - `calculate_surcharge.py`, `tools/models.py`, `state.py`, `graph.py` are byte-for-byte unchanged (`git diff --stat` shows zero changes for those paths).
    - All 5 pre-existing tests in `test_pricing_agent.py` still pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update SYSTEM_PROMPT to teach the LLM the bullet contract</name>
  <files>backend/agent/prompts/pricing_agent.py</files>
  <action>
    Replace the existing `SYSTEM_PROMPT` constant with a version that:

    1. **Keeps the role line** ("You are the Pricing Agent for Express's surcharge orchestrator.") and the constraint that the LLM must use only the values it's given (anti-hallucination).

    2. **Replaces the 1-sentence rule** with a multi-step rule set:
       - Output a JSON object with TWO keys: `summary` (one short sentence ≤30 words, kept for backward compat) and `bullets` (a list of 3-5 short strings).
       - Each bullet is one signal: base rate, fuel delta + volatility, traffic (only when shipping_type is bounce), market/news context (only when search_context is provided), final surcharge + total.
       - Use ONLY the numbers in the input payload — do not invent or recompute.
       - When `capped` is true, the final bullet must mention the cap or floor.
       - Bullets must be plain text, no markdown bullet prefix (the node will add `- ` when rendering).
       - Each bullet under 25 words.

    3. **Documents the input payload shape** the node will pass — a single JSON message with keys: `rate`, `surcharge`, `fuel_data`, `route_data`, `shipping_type`, `volatility_flag` (one of low/normal/high), `search_context_summary` (string or null), `seed_bullets` (the deterministic bullets the node already built — the LLM may copy or rephrase them).

    4. **Includes a one-shot example** in the prompt showing a valid JSON output with both `summary` and a 4-bullet `bullets` list (high volatility + bounce + no news).

    5. **DO NOT** add any directive that would change the formula or contradict the deterministic numbers — the LLM is a *narrator*, not a recalculator.

    Keep the file's `__all__ = ["SYSTEM_PROMPT"]` and `from __future__ import annotations` lines.

    **Critical:** the `summary` field MUST remain in the contract (D-04 backward compat). Any prompt change that drops `summary` will break the existing `test_computes_surcharge_and_emits_trace` test, which exercises a scripted LLM emitting `'{"summary": "..."}'` with no bullets — the node must still parse that gracefully (defaults bullets to []). The Task 1 LLM-parse path already handles this via `bullets: list[str] = Field(default_factory=list)`; this prompt change is informational to the LLM only.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && .venv/bin/python -c "from backend.agent.prompts.pricing_agent import SYSTEM_PROMPT; assert 'bullets' in SYSTEM_PROMPT and 'summary' in SYSTEM_PROMPT and 'volatility_flag' in SYSTEM_PROMPT and 'search_context' in SYSTEM_PROMPT, SYSTEM_PROMPT"</automated>
  </verify>
  <done>
    - `SYSTEM_PROMPT` mentions `bullets`, `summary`, `volatility_flag`, and `search_context_summary` (or `search_context`) explicitly.
    - The prompt instructs 3-5 bullets, no invented numbers, cap/floor mention when `capped`.
    - Includes a one-shot JSON example with both keys filled.
    - Existing `test_computes_surcharge_and_emits_trace` still passes (the LLM stub returns `{"summary": "..."}` with no bullets — the node handles this via the schema default).
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add tests for bullets, volatility, search_context, and bullet-shaped fallback</name>
  <files>backend/tests/test_pricing_agent.py</files>
  <behavior>
    Add 4 NEW test functions (the existing 5 stay untouched):

    1. **`test_emits_bullet_reasoning`** — happy path with scripted LLM returning both `summary` and a 4-bullet `bullets` list. Asserts:
       - `entry["reasoning"]` is a string starting with `- `.
       - `entry["reasoning"]` contains `\n- ` at least 2 times (≥3 bullets total).
       - `entry["reasoning"]` mentions the rate tier `"11-25kg"`, the surcharge `total` numerically, AND the word `volatility`.
       - LLM bullets are preserved when valid (assert at least one of the LLM's verbatim bullet substrings is present).

    2. **`test_bullets_drop_traffic_for_retail_standard`** — same scripted LLM, but `state["shipping_type"] = "retail_standard"` and traffic_severity ignored. Asserts:
       - The reasoning string does NOT contain the word `"traffic"` (case-insensitive).
       - Bullet count (lines starting with `- `) is exactly 3 (no traffic, no search_context — base + fuel/volatility + final).

    3. **`test_bullets_include_search_context_when_present`** — state has `search_context = {"query": "diesel news", "summary": "Brent up 3% on OPEC cuts.", "sources": [], "fetched_at": "2026-05-09T03:00:00Z"}`. Asserts:
       - The reasoning string contains a substring of the search summary (e.g., `"Brent up 3%"` or `"OPEC cuts"`).
       - When `search_context` is `None` or omitted, the reasoning does NOT contain those substrings (parametrize or write a sibling assertion).

    4. **`test_bullet_shaped_deterministic_fallback`** — mirror of the existing `test_gemini_failure_deterministic_fallback`, but asserts the BULLET shape:
       - LLM raises `RuntimeError` → fallback fires.
       - `entry["reasoning"]` starts with `- ` and has ≥3 bullet lines.
       - `entry["status"] == "ok"` (D-11 invariant preserved).
       - Reasoning contains the rate tier, the volatility flag word (`low|normal|high`), and the surcharge total — proving fallback bullets carry the same signals as LLM bullets.

    Add a small helper at the top of the new tests block:
    ```python
    def _bullet_count(reasoning: str) -> int:
        return sum(1 for line in reasoning.splitlines() if line.startswith("- "))
    ```

    Where the volatility flag must be deterministic for assertions, monkeypatch `mod._compute_volatility_flag` to return a known string (e.g., `"normal"`) — avoids coupling tests to live CSV state. (Live CSV is also exercised implicitly by the other tests since the helper is wrapped in try/except; flake-resistance.)

    All scripted LLM responses for the new tests should emit BOTH keys, e.g.:
    ```python
    '{"summary": "Surcharge 4% = 124.80 THB.", "bullets": ['
    '"Base rate 120.00 THB (11-25kg tier, zone central-1, bounce).",'
    '"Diesel at 31.00 THB/L vs baseline 29.94 (+3.54% delta, volatility normal over last 7 days).",'
    '"Bangkok Metro traffic severity 2/5 adds a per-step bump.",'
    '"Final surcharge 4.00% = 4.80 THB; total 124.80 THB."'
    ']}'
    ```
  </behavior>
  <action>
    Append the four new test functions and the `_bullet_count` helper to `backend/tests/test_pricing_agent.py`. Reuse the existing `_full_state()` and `_scripted_llm()` helpers — do NOT duplicate them.

    For each new test:
    - Use `mocker.patch.object(mod, "lookup_rate", return_value=RateResult(base_rate=120.0, currency="THB", rate_tier="11-25kg"))`.
    - Use `monkeypatch.setattr(mod, "_compute_volatility_flag", lambda *a, **kw: "normal")` to pin the flag (or `"high"` where the test variant needs it).
    - For `test_bullet_shaped_deterministic_fallback`, use the existing `_BrokenLLM` pattern from `test_gemini_failure_deterministic_fallback`.

    Ensure the existing 5 tests are NOT modified — git diff for this task should show only ADDED lines (plus the import for `_bullet_count` if needed, but you can keep the helper local-only).

    Run the full suite, not just the pricing tests, to confirm no regression elsewhere.
  </action>
  <verify>
    <automated>cd /Users/pollot/Desktop/express-dynamic-workflow && .venv/bin/python -m pytest backend/tests/test_pricing_agent.py -v -q 2>&1 | tail -30 && .venv/bin/python -m pytest backend/tests -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - `backend/tests/test_pricing_agent.py` has 9 test functions total (5 old + 4 new).
    - All 9 pricing tests pass.
    - Full backend suite (`pytest backend/tests`) passes — no collateral breakage in graph/API/HITL tests that exercise the pricing node indirectly.
    - The 5 pre-existing test functions (`test_computes_surcharge_and_emits_trace`, `test_bubbles_value_error_from_lookup_rate`, `test_gemini_failure_deterministic_fallback`, `test_guards_missing_route_data`, `test_guards_missing_fuel_data`) are byte-for-byte unchanged in the diff.
    - `pytest backend/tests/test_fuel_prices.py` (formula auto-eval coverage) and any test referencing `calculate_surcharge` still pass.
  </done>
</task>

</tasks>

<verification>

**Phase-level verification (run after all 3 tasks):**

1. **Formula contract intact:**
   ```bash
   cd /Users/pollot/Desktop/express-dynamic-workflow && git diff --stat backend/agent/tools/calculate_surcharge.py backend/agent/tools/models.py backend/agent/state.py backend/agent/tools/calculate_surcharge_tool.py
   ```
   Expected: zero output (no changes to locked files).

2. **All backend tests green:**
   ```bash
   cd /Users/pollot/Desktop/express-dynamic-workflow && .venv/bin/python -m pytest backend/tests -q
   ```
   Expected: all tests pass; pricing_agent test count went from 5 to 9.

3. **Live smoke (informational, not a gate):**
   Run a chat turn locally and inspect the trace panel for the pricing step — the bullet list should display in the expanded trace step. Skip if uvicorn isn't running; tests are the gate.

4. **OBS-03 auto-eval still wires:**
   ```bash
   .venv/bin/python -m pytest backend/tests -k "auto_eval or formula_accuracy or post_formula" -q
   ```
   Expected: all related tests pass — confirms the OBS-03 block in `pricing_agent_node` remains untouched.

5. **No new external-API imports:**
   ```bash
   .venv/bin/python -c "import ast, pathlib; tree = ast.parse(pathlib.Path('backend/agent/nodes/pricing_agent.py').read_text()); imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]; names = sorted({(n.module if isinstance(n, ast.ImportFrom) else n.names[0].name) for n in imports}); banned = [n for n in names if n and (n.startswith('googlemaps') or n.startswith('tavily') or n.startswith('httpx') or n.startswith('requests'))]; assert not banned, f'BANNED IMPORT: {banned}'; print('imports clean:', names)"
   ```
   Expected: no googlemaps / tavily / httpx / requests imports — confirms D-03 (existing state only, no new API calls).

</verification>

<success_criteria>

- `PricingReasoning` schema has both `summary: str` and `bullets: list[str]` fields.
- `_compute_volatility_flag` exists, is pure, returns `"low"|"normal"|"high"`, never raises on missing/malformed CSV.
- Pricing trace `reasoning` field is a multi-line string of `- bullet` lines (3 bullets minimum, 5 maximum).
- The bullet structure adapts to context: traffic bullet only for `bounce`; news bullet only when `state["search_context"]` has a non-empty summary.
- Deterministic fallback emits the SAME bullet shape as the LLM path (D-11 contract preserved AND enriched).
- `backend/agent/tools/calculate_surcharge.py` is unchanged (formula locked).
- All 5 pre-existing pricing tests pass without modification.
- 4 new tests added, all 9 pricing tests pass.
- Full backend test suite passes (currently 248 tests per STATE 260509-eum baseline; should grow to ~252 with the new tests).
- No new external-API imports added to `pricing_agent.py`.
- Visible reasoning step count in the trace panel grows from 1 line ("Surcharge 4% on 120 THB base = 124.80 THB.") to 3-5 bulleted steps that walk a user through every signal the agent weighed — fulfilling the "agentic feel" objective.

</success_criteria>

<output>
After completion, create `.planning/quick/260509-uwb-upgrade-pricing-agent-to-visibly-reason-/260509-uwb-SUMMARY.md` documenting:
- The 3-bullet/4-bullet/5-bullet rendering shape with one example per shape (retail vs bounce vs bounce+news).
- The volatility threshold (>0.5 * mean_abs_delta = high; <0.2 = low; else normal) and rationale.
- Confirmation that formula tests (calculate_surcharge.py and formula_accuracy auto-eval) remain green.
- Test count delta (5 → 9 in test_pricing_agent.py).
- Any deviation from CONTEXT.md decisions and why.
</output>
