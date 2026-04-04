# Research Summary: Express Dynamic Surcharge Orchestrator

**Domain:** Multi-agent LangGraph orchestrator for logistics surcharge calculation
**Researched:** 2026-04-04
**Overall confidence:** MEDIUM (training data only; web search and fetch tools were unavailable for version verification)

## Executive Summary

The chosen stack -- LangGraph + Gemini 2.0 Flash + FastAPI + Next.js 15 + SQLite + Langfuse -- is well-matched for this project. Each technology has a clear role, and the stack avoids overengineering while demonstrating sufficient technical depth for grading. The critical insight is that version alignment within the LangChain ecosystem (langgraph, langchain-core, langchain-google-genai) is the single biggest integration risk.

The architecture follows a **supervisor pattern** with a Planner node that routes to three specialist agents (Fuel, Route, Pricing) via LangGraph conditional edges. Fuel and Route agents can execute in parallel via the Send API. All numerical computation happens in deterministic Python tool functions -- the LLM handles intent detection and natural language synthesis only. This separation is essential for correctness and testability.

The most dangerous pitfalls are: (1) Gemini Flash producing unreliable structured output, requiring validation wrappers on every LLM call; (2) SSE streaming from FastAPI to Next.js requiring `fetch()` with `ReadableStream` instead of the `EventSource` API (which is GET-only); (3) EPPO fuel data source being fragile, requiring a tested multi-level fallback chain from day one; and (4) LangChain package version misalignment causing cryptic import errors.

The frontend should be treated as a thin rendering layer. Next.js 15 with React 19 should use Client Components for all FastAPI data fetching -- do not use Server Actions, Server Components for API calls, or Next.js API routes. The backend is FastAPI; Next.js is purely the UI.

## Key Findings

**Stack:** LangGraph + langchain-google-genai + FastAPI + sse-starlette + Next.js 15 + SQLite + Langfuse. Use `langchain-google-genai` (NOT raw `google-generativeai`) for LangGraph compatibility.
**Architecture:** Supervisor pattern with parallel fan-out via Send API, state-driven routing, tool-computed outputs, SQLite checkpointer for memory.
**Critical pitfall:** Install all LangChain ecosystem packages together in one `pip install` command to let pip resolve compatible versions. Mixing versions causes silent breakage.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Foundation & Data Pipeline** - State schema, Pydantic models, SQLite setup, seed scripts, `.env.example`
   - Addresses: Rate table, zone definitions, database schema, environment configuration
   - Avoids: Building nodes without a stable state contract or data to test against

2. **Tools & Individual Agents** - Build and test each tool independently, then wrap in agent nodes
   - Addresses: Fuel fallback chain, route caching with mocks, surcharge formula, rate lookup
   - Avoids: Integration bugs from untested tools; Google Maps budget burn (use mocks)

3. **Graph Assembly & API Layer** - Wire nodes into StateGraph, conditional edges, checkpointer, FastAPI SSE endpoint
   - Addresses: Orchestration, conversation memory, SSE streaming proof-of-concept
   - Avoids: Frontend work before API is stable; debugging graph wiring and SSE simultaneously

4. **Frontend & Reasoning Trace** - Next.js chat UI, reasoning trace panel, SSE consumption
   - Addresses: Chat interface, trace visibility (core grading criterion), feedback buttons
   - Avoids: Over-engineering with Server Components; reasoning trace as afterthought

5. **Polish & Observability** - Parallel agents (Send API), HITL gate, Langfuse integration, dashboard, Tavily search
   - Addresses: Differentiator features, bonus mark categories, observability
   - Avoids: Scope creep into polish before core works

**Phase ordering rationale:**
- Each phase depends on the previous one completing (data -> tools -> graph -> API -> UI)
- Data pipeline first ensures tools have data to work with during development
- Tools tested in isolation before being wired into the graph prevents compound debugging
- SSE streaming must be proven end-to-end before building the full chat UI
- Observability (Langfuse) is additive and must be optional (never a hard dependency)

**Research flags for phases:**
- Phase 2: Verify Gemini structured output reliability with `langchain-google-genai` before building all agent nodes
- Phase 3: Verify exact LangGraph Send API semantics and `astream_events` v2 event schema against installed version
- Phase 3: Test SSE end-to-end (FastAPI -> browser fetch/ReadableStream) before investing in UI

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack choices | HIGH | Locked by project constraints; technologies are well-matched |
| Package versions | LOW | Based on training data (cutoff May 2025); must verify with `pip index versions` and `npm view` |
| Features | HIGH | Well-defined in PROJECT.md and architecture doc |
| Architecture | MEDIUM | Patterns are sound but LangGraph API details (Send, interrupt_before, astream_events) need version verification |
| Pitfalls | MEDIUM | Based on common multi-agent system failure modes, not project-specific post-mortems |

## Gaps to Address

- **Package versions must be verified at install time.** All version numbers in STACK.md are estimates from training data. Run `pip index versions langgraph` and similar before pinning.
- **EPPO API documentation and actual response format** needed for the fuel price tool implementation. May need to scrape and reverse-engineer the data source.
- **Gemini 2.0 Flash structured output support via `langchain-google-genai`** -- test `with_structured_output()` early to determine if function calling or JSON mode works better.
- **Langfuse v2 vs v3 callback handler import path** -- the SDK may have changed its LangChain integration module.
- **Tailwind v4 vs v3 compatibility with Next.js 15** -- if `create-next-app` scaffolds v4 and it causes friction, fall back to v3.
- **LangGraph `langgraph-checkpoint-sqlite` async variant** -- verify import path (`langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver` vs alternatives).
