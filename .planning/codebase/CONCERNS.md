# Codebase Concerns

**Analysis Date:** 2026-04-04

## Project Status: Scaffold Phase

This codebase is **early-stage** — only directory structure and documentation exist. No production code has been implemented. The concerns below address both **structural gaps** and **architectural risks** for the implementation phase.

---

## Critical Implementation Gaps

**Core Agent Logic Not Implemented:**
- Issue: All agent nodes are stubbed (`backend/agent/nodes/__init__.py`, `backend/agent/tools/__init__.py`, `backend/agent/prompts/__init__.py` are empty)
- Files: `backend/agent/nodes/`, `backend/agent/tools/`, `backend/agent/prompts/`
- Impact: No actual LangGraph orchestration, tool execution, or agent routing logic exists. The entire system needs implementation.
- Fix approach: Implement LangGraph multi-agent graph with Planner, Fuel Agent, Route Agent, Pricing Agent per docs/architecture.md

**Backend API Not Implemented:**
- Issue: `/api/chat`, `/api/conversations`, `/api/feedback` endpoints described in docs/architecture.md do not exist
- Files: `backend/api/__init__.py` is empty
- Impact: Frontend cannot call backend; entire chat workflow is non-functional
- Fix approach: Implement FastAPI endpoints per API specification in docs/architecture.md with SSE streaming for chat

**Backend Entry Point Missing:**
- Issue: No `backend/main.py` or `backend/app.py` exists; FastAPI application not initialized
- Files: Missing `backend/main.py`
- Impact: `uvicorn main:app` command in README will fail
- Fix approach: Create FastAPI app with CORS, route registration, database initialization, Langfuse callback setup

**Frontend Components Not Implemented:**
- Issue: `frontend/.gitkeep` only; no Next.js app, React components, or UI exists
- Files: `frontend/` is empty
- Impact: No chat interface, trace panel, charts, or feedback mechanism
- Fix approach: Create Next.js 15 app with chat UI, trace viewer, fuel price chart, feedback UI per architecture.md

**Data Pipeline Scripts Missing:**
- Issue: Referenced scripts `data/scripts/fetch_fuel_prices.py`, `generate_rate_table.py`, `seed_database.py` do not exist
- Files: `data/scripts/` contains only `.gitkeep`
- Impact: Setup instructions in README (lines 123-129) will fail; no database seeding possible
- Fix approach: Implement all three scripts with proper error handling and data validation

**Database Schema Missing:**
- Issue: SQLite database design for rate tables and conversation checkpoints not defined; no schema file
- Files: Missing `data/schema.sql` or migration system
- Impact: `seed_database.py` cannot populate tables without schema; conversation memory will not work
- Fix approach: Create SQL schema file with rate table, conversation, and checkpoint tables; document in schema.sql

**Requirements File Missing:**
- Issue: No `backend/requirements.txt` or `frontend/package.json` defined
- Files: Missing `backend/requirements.txt`, `frontend/package.json`
- Impact: `pip install -r requirements.txt` and `npm install` commands in README (lines 105, 111) will fail
- Fix approach: Create both files with exact dependency versions; pin LangGraph, FastAPI, Gemini SDK versions

---

## Tech Debt: Hardcoded Configuration

**Surcharge Multipliers Hardcoded in Logic:**
- Issue: Shipping type multipliers (bounce: 1.0, retail_fast: 0.8, retail_standard: 0.5) documented in docs/architecture.md line 173-176 are not parameterized
- Files: Not yet implemented; will be in `backend/agent/nodes/` or `backend/services/`
- Impact: Changes to multipliers require code changes; no per-customer or per-region customization
- Fix approach: Move multipliers to environment variables or database config table; load at startup

**Baseline Diesel Price Hardcoded:**
- Issue: `BASELINE_DIESEL_PRICE=29.94` is an environment variable (good), but no validation or update mechanism exists
- Files: `.env.example` line 23
- Impact: If baseline becomes stale, system will calculate incorrect surcharges; no audit trail of baseline changes
- Fix approach: Add database table to track baseline changes over time with timestamp; provide admin endpoint to update

**Hard Caps on Surcharge (15% max, -5% min):**
- Issue: Caps documented in docs/architecture.md line 184-185; not parameterized per customer/region
- Files: Not yet implemented; will be in pricing logic
- Impact: Single cap for all customers; large B2B customers may need different caps; no flexibility for regional pricing
- Fix approach: Add surcharge_cap and surcharge_floor to rate table; lookup per shipping type + zone

**Fuel Price API Fallback Relies on CSV Data:**
- Issue: docs/architecture.md line 279 describes fallback to "latest row from CSV" if API fails
- Files: Not yet implemented; described in tool implementation area
- Impact: Stale data (24hr lag mentioned in README line 185); no way to know if using live or fallback data
- Fix approach: Implement dual-source strategy with explicit flag in response; log fallback usage to monitoring

---

## Known Limitations (From README)

**Fuel Price Data Lag:**
- Issue: EPPO data has 1-day lag; PTT scraping depends on website availability (README line 185)
- Files: Not yet implemented, but described in data pipeline
- Impact: Surcharge recommendations may be based on yesterday's prices during volatile markets
- Risk level: Medium
- Recommendation: Implement historical trend analysis to warn when prices are changing rapidly; consider premium fuel data sources

**Zone Mapping Oversimplified:**
- Issue: Three zones (central-1, central-2, central-3) cover entire Central Region; may not reflect traffic/distance costs accurately
- Files: Not yet implemented; referenced in docs/architecture.md line 139-140
- Impact: Zone 3 has wide variance in delivery costs; oversimplification may reduce pricing accuracy
- Risk level: Low
- Recommendation: Validate zone boundaries against actual delivery cost data after launch; consider adding sub-zones if needed

**Rate Table is Simulated:**
- Issue: README line 186 states rate table is "simulated based on assumptions — not actual Express pricing"
- Files: `data/raw/express_rate_table.csv` will be generated by unimplemented `generate_rate_table.py`
- Impact: System may recommend surcharges that don't align with actual Express business model
- Risk level: High
- Recommendation: Document assumptions in `data/scripts/generate_rate_table.py`; migrate to real rate data in Phase 2

**LLM Rate Limits:**
- Issue: Gemini free tier is 15 RPM (README line 189); insufficient for production traffic
- Files: Not yet implemented; will be in backend initialization
- Impact: Demo only; will throttle or fail under moderate load
- Risk level: Medium
- Recommendation: Plan migration to paid tier or batching/caching strategy before production launch

**Central Region Only:**
- Issue: System covers 6 provinces; no northern, southern, or northeastern Thailand coverage
- Files: Zone definitions in docs/architecture.md line 266-271; hardcoded in route tool
- Impact: Cannot scale to other regions without substantial work; zone mapping must be rewritten
- Risk level: Low (acknowledged limitation)
- Recommendation: Design zone system as pluggable per region to reduce refactor cost when expanding

---

## Security Considerations

**No Input Validation Framework:**
- Issue: Tool inputs (origin, destination, shipping_type, weight_kg) described in docs/architecture.md not validated
- Files: Not yet implemented; will be in `backend/agent/tools/`
- Risk: Invalid inputs could crash tools or produce nonsensical surcharges
- Recommendation: Implement Pydantic models for all tool inputs with strict validation

**API Key Management:**
- Issue: Five API keys required (.env.example lines 2-11); no key rotation, audit logging, or emergency revocation mechanism
- Files: `.env.example`
- Risk: Key compromise has no containment; keys are plain-text in .env
- Recommendation: Use environment-based secrets management (e.g., Python-dotenv for dev, cloud secrets in production); add key rotation schedule

**No SQL Injection Protection:**
- Issue: SQLite queries will be written in tool implementations; no mention of parameterized queries in architecture.md
- Files: Not yet implemented; will be in rate lookup and checkpoint storage
- Risk: User input (origin, destination) could be passed to SQL; requires parameterization
- Recommendation: Use ORM (SQLAlchemy) or strict parameterized queries; never concatenate user input into SQL

**LLM Injection Risk:**
- Issue: Tool outputs returned to LLM without sanitization; user queries echoed in prompts without escaping
- Files: Not yet implemented; will be in agent prompt engineering
- Risk: Adversarial fuel price data or user messages could cause LLM to return unsafe recommendations
- Recommendation: Validate tool outputs before returning to LLM; sanitize user input before passing to prompts

**Conversation Memory Unencrypted:**
- Issue: `data/checkpoints.db` stores full conversation history in SQLite (architecture.md line 192); no encryption at rest
- Files: Not yet implemented
- Risk: Database breach exposes all conversation data including route information and customer details
- Recommendation: Encrypt sensitive fields (origin, destination, customer type) in checkpoints using database-level or field-level encryption

---

## Performance Bottlenecks

**No Tool Result Caching Beyond State:**
- Issue: docs/architecture.md line 202-205 describes "tool result cache in AgentState" with 1-hour TTL for fuel data, but no distributed cache backend
- Files: Not yet implemented; will be in `backend/agent/`
- Impact: Each new conversation or after 1 hour, full tool calls happen; no cross-conversation caching of stable data (rates, routes)
- Fix approach: Add Redis or in-process LRU cache for frequently called tools (route calculations, rate lookups)

**Google Maps API Rate Limits:**
- Issue: Route calculations hit Google Maps API for every route query (docs/architecture.md line 141); no circuit breaker
- Files: Not yet implemented
- Impact: 100 concurrent users could rapidly exhaust Maps quota; system fails gracefully with fallback?
- Fix approach: Implement exponential backoff + circuit breaker for Maps API; pre-cache common routes

**Fuel Price API Rate Limits:**
- Issue: Fuel Agent calls API per chat query; EPPO and PTT have undocumented rate limits
- Files: Not yet implemented
- Impact: High-traffic periods could exhaust API quota; fallback to stale CSV data
- Fix approach: Implement 1-hour in-memory cache for fuel prices; store in-memory with file persistence

**No Database Indexing Strategy:**
- Issue: SQLite schema not yet designed; no mention of indexes on rate table or checkpoint lookups
- Files: Missing `data/schema.sql`
- Impact: Queries like "lookup_rate(bounce, central-2, 150kg)" could be O(n) without proper indexes
- Fix approach: Add indexes on (shipping_type, zone, weight_kg) for rate table; (thread_id, timestamp) for checkpoints

**LLM Latency Unknown:**
- Issue: docs/architecture.md line 234 mentions "target: < 10s" but no profiling data; Gemini free tier responsiveness unknown
- Files: Not yet implemented; will need production testing
- Impact: Some queries may take 10+ seconds for users; no timeout mechanism documented
- Fix approach: Add request timeouts (30s hard limit); implement response time SLA tracking in Langfuse

---

## Fragile Areas

**Multi-Agent Coordination Fragility:**
- Issue: Agent graph routing (conditional edges in docs/architecture.md line 112-122) not yet implemented; complex state machine
- Files: Not yet implemented; will be in `backend/agent/`
- Why fragile: Conditional routing ("fetch_fuel" vs "calculate_price" vs "clarify") depends on perfect state management and agent decision-making
- Safe modification: Add comprehensive logging at each router decision point; test extensively with scenario matrix (missing weight, ambiguous route, etc.)
- Test coverage gaps: No test cases for edge cases (what if user asks about "distance" without origin/destination? What if fuel data fails?)

**Surcharge Calculation Logic:**
- Issue: Multi-step calculation (docs/architecture.md line 166-186) with traffic adjustments, multipliers, caps not yet implemented
- Files: Not yet implemented; will be in `backend/services/` or agent tools
- Why fragile: Off-by-one errors, cap logic bugs, or multiplier misapplication directly affects pricing accuracy
- Safe modification: Implement formula as pure function with 100% test coverage; add integration test against Excel reference
- Test coverage gaps: No unit tests for cap behavior, no tests for edge cases (0% fuel delta, negative weight)

**Zone Determination from Route:**
- Issue: docs/architecture.md line 139-140 describes "zone mapping based on origin-destination pair"; implementation not specified
- Files: Not yet implemented; will be in `calculate_route` tool
- Why fragile: Hardcoded if/else logic for zone determination could miss edge cases or new areas
- Safe modification: Move zone definitions to database table; lookup zone by origin-destination pair
- Test coverage gaps: No tests for all possible origin-destination pairs in central region

**Data Seeding Pipeline:**
- Issue: Three scripts (`fetch_fuel_prices.py`, `generate_rate_table.py`, `seed_database.py`) not yet implemented; manual CSV/SQL dependencies
- Files: `data/scripts/` is empty
- Why fragile: Manual data pipeline prone to operator error; no validation that data loaded correctly
- Safe modification: Add checksums/hashes to validate data integrity; implement idempotent seeding with rollback
- Test coverage gaps: No tests for broken CSV files, missing columns, or data type mismatches

**Environment Variable Dependency:**
- Issue: Eight env vars required (.env.example); no validation that all are set before startup
- Files: `.env.example`
- Why fragile: Missing API key causes cryptic errors at runtime; no startup validation
- Safe modification: Add startup health checks that validate all required env vars present and API keys are live (test calls)
- Test coverage gaps: No tests for missing/invalid env var scenarios

---

## Testing Infrastructure Gaps

**No Test Framework Configured:**
- Issue: No `pytest.ini`, `vitest.config.ts`, or test runner setup
- Files: Not yet created
- Impact: Unclear how tests should be organized or run
- Recommendation: Add pytest for backend (with fixtures for test data), Vitest for frontend; define test directory structure

**No Fixtures or Test Data:**
- Issue: Mocking strategy for external APIs (Gemini, Google Maps, Tavily) not documented
- Files: Not yet created; documented in architecture.md but no implementation
- Impact: Tests will hit real APIs; expensive and slow
- Recommendation: Create test fixtures for all external API responses; use pytest fixtures for dependency injection

**No Test Database Strategy:**
- Issue: SQLite database design not finalized; no test database isolation plan
- Files: Not yet implemented
- Impact: Tests could contaminate development database
- Recommendation: Use in-memory SQLite for tests; auto-reset between test runs

**Frontend Testing Not Planned:**
- Issue: Chat UI, trace viewer, feedback components not yet created; no mention of React testing (React Testing Library, Playwright)
- Files: Not yet created
- Impact: Frontend code will accumulate bugs without test coverage
- Recommendation: Plan React component tests (unit) and e2e tests (Playwright) for critical paths (chat submission, feedback)

---

## Missing Critical Features

**No Conversation Resumption UI:**
- Issue: docs/architecture.md line 210-212 describes `/api/conversations` and `/api/conversations/:id` endpoints, but frontend not built
- Files: Frontend not implemented
- Impact: Users cannot resume past conversations; must start fresh each session
- Recommendation: Implement conversation sidebar in frontend showing past threads with timestamps; validate in e2e tests

**No Surcharge History Tracking:**
- Issue: README line 197 mentions "historical surcharge tracking and trend analysis" as future improvement; no current system to store or compare historical surcharges
- Files: Not yet implemented
- Impact: Cannot track surcharge recommendation accuracy over time
- Recommendation: Add surcharge_history table to database; log every calculation with inputs for audit trail

**No Admin Panel for Configuration:**
- Issue: Surcharge caps, baseline price, multipliers are environment variables; no runtime update mechanism
- Files: Not yet implemented
- Impact: Requires redeploy to change pricing parameters; no emergency adjustment capability
- Recommendation: Create admin endpoints to update baseline price, caps, and multipliers at runtime; log all changes

**No Error Recovery or Retry UI:**
- Issue: When a tool fails (Maps API timeout, Gemini rate limit), system falls back silently per docs/architecture.md line 278-281; no user feedback on data freshness
- Files: Not yet implemented
- Impact: Users don't know surcharge is based on stale/fallback data
- Recommendation: Add warning banner in response when using fallback data; offer "retry" button for user to refresh

**No Rate Limiting or Quota Management:**
- Issue: No mention of per-user or per-API-key rate limits
- Files: Not yet implemented
- Impact: Abusive users could exhaust API quotas; no protection against denial of service
- Recommendation: Implement rate limiting middleware (FastAPI slowapi); add quota tracking per user/API key

---

## Deployment Concerns

**No Containerization:**
- Issue: No Dockerfile or docker-compose.yml
- Files: Missing; expected at project root
- Impact: Local dev works; production deployment requires manual setup; inconsistent environments
- Fix approach: Create Dockerfile for backend (Python 3.11) and frontend (Node 18); docker-compose for local dev with SQLite volume

**No Production Configuration:**
- Issue: Hardcoded paths (`data/express.db`, `data/checkpoints.db`) in architecture.md; no env override
- Files: Not yet implemented
- Impact: Cannot easily move database to different location for production
- Fix approach: Make all paths configurable via env vars; document prod deployment checklist

**No Database Migration System:**
- Issue: No Alembic or Flyway setup; schema changes require manual SQL
- Files: Not yet implemented
- Impact: Adding new tables/columns in future updates is error-prone; no rollback capability
- Fix approach: Set up Alembic for schema versioning; require migrations for all schema changes

**No Startup Health Checks:**
- Issue: Backend startup does not validate database connectivity, API key liveness, or required services
- Files: Not yet implemented
- Impact: Service appears healthy but APIs are broken; takes time to discover in production
- Fix approach: Add `/health` and `/health/deep` endpoints that test database, LLM API, Maps API, etc.

---

## Architectural Risks

**LangGraph Dependency:**
- Issue: Entire agent orchestration depends on LangGraph library; switching frameworks would require rewrite
- Files: All agent implementation will use LangGraph
- Risk: LangGraph version updates could break agent graph; library may diverge from project needs
- Mitigation: Pin LangGraph version in requirements.txt; plan feature set before committing to version; consider feature-flag for experimental routing

**Gemini API Lock-in:**
- Issue: All reasoning depends on Google Gemini 2.0 Flash; switching LLMs would require prompt rewrites
- Files: Will be configured in backend initialization
- Risk: Gemini changes pricing, availability, or API; free tier removed; performance degrades
- Mitigation: Abstract LLM behind interface; allow swapping Gemini for Claude/OpenAI with config change; test with multiple models

**SQLite Scalability Limit:**
- Issue: Architecture uses SQLite for both rate tables and conversation checkpoints
- Files: `data/express.db` and `data/checkpoints.db`
- Risk: SQLite has write concurrency limits; cannot scale beyond single-server deployment
- Recommendation: Start with SQLite; migrate to PostgreSQL when scaling beyond 100 concurrent users

**Rate Table Brittleness:**
- Issue: All pricing depends on rate table in CSV → database pipeline; no versioning
- Files: `data/raw/express_rate_table.csv` (to be generated), `seed_database.py` (not implemented)
- Risk: Accidental rate table corruption or upload of wrong version breaks all pricing
- Recommendation: Version rate tables with timestamps; require checksums; maintain backup of previous version

---

## Monitoring and Observability Gaps

**Langfuse Integration Not Yet Wired:**
- Issue: Architecture.md line 217-226 describes Langfuse integration but no code yet implements callbacks
- Files: Will be in `backend/agent/` initialization
- Impact: No production visibility into agent behavior, latency, or failures until implemented
- Fix approach: Add LangfuseCallbackHandler to all LangGraph invocations; validate traces appear in Langfuse dashboard

**No Structured Logging:**
- Issue: No mention of logging framework or log format standards
- Files: Not yet implemented
- Impact: Debugging production issues will be difficult; logs scattered across console output
- Recommendation: Use Python logging with JSON format (structlog); include request ID, tool name, latency in every log

**No Metrics/Dashboards:**
- Issue: No Prometheus metrics, CloudWatch dashboard, or data warehouse for analytics
- Files: Not yet implemented
- Impact: Cannot track system health, surcharge distribution, or user patterns
- Recommendation: Add metrics for: query count, latency (p50/p95/p99), tool success rate, API error rate; expose on /metrics

**No Alerting:**
- Issue: No mechanism to alert on API failures, rate limit exhaustion, or anomalies
- Files: Not yet implemented
- Impact: Silent failures could go unnoticed; emergency manual intervention required
- Recommendation: Configure alerts for: Maps API quota exhaustion, Gemini rate limits, database connectivity, response time SLA breaches

---

## Process and Documentation Gaps

**Incomplete README:**
- Issue: README has multiple unfinished sections (lines 14-19, 179)
  - Team member information not filled (IT Lead student ID, names, other members)
  - "Vibe-Coding Tools Used" incomplete (line 179 has "TODO: Add others")
- Files: `README.md`
- Impact: Documentation is not authoritative for team; onboarding unclear
- Fix approach: Complete team roster with actual student IDs and names; update tools list when project work is done

**No Deployment Runbook:**
- Issue: README describes setup but no "Deploy to Production" section
- Files: No deployment documentation
- Impact: Team must figure out production deployment from scratch
- Recommendation: Create `docs/DEPLOYMENT.md` with step-by-step prod launch checklist, rollback procedure, emergency contact

**No Troubleshooting Guide:**
- Issue: No FAQ or common issues documentation
- Files: Not yet created
- Impact: Users and developers encounter same issues repeatedly
- Recommendation: Create `docs/TROUBLESHOOTING.md` with common errors and fixes (e.g., "Maps API quota exceeded", "Gemini rate limit", "Database locked")

**No API Documentation:**
- Issue: Architecture.md line 296-304 lists endpoints but no OpenAPI/Swagger spec
- Files: Not yet created
- Impact: Frontend developers must read code to understand API contract
- Recommendation: Generate OpenAPI spec from FastAPI automatically; expose on `/docs` endpoint

---

## Summary Table: Risk by Priority

| Area | Severity | Status | Est. Fix Time |
|------|----------|--------|---------------|
| Core Agent Logic Missing | Critical | Not Started | 4-5 days |
| Backend API Not Implemented | Critical | Not Started | 2-3 days |
| Frontend Not Implemented | Critical | Not Started | 3-4 days |
| Database Schema Missing | Critical | Not Started | 0.5 days |
| Requirements Files Missing | High | Not Started | 0.5 days |
| Data Pipeline Scripts Missing | High | Not Started | 1-2 days |
| Input Validation Not Planned | High | Not Started | 1 day |
| Surcharge Multipliers Hardcoded | High | Not Started | 0.5 days |
| Tool Caching Beyond State Missing | Medium | Not Started | 1 day |
| Test Framework Not Set Up | Medium | Not Started | 0.5 days |
| Containerization Missing | Medium | Not Started | 0.5 days |
| Zone Mapping Oversimplified | Medium | Not Started | Ongoing |
| Langfuse Integration Not Wired | Medium | Not Started | 0.5 days |
| Conversation Resumption UI Missing | Low | Not Started | 1 day |
| Admin Configuration UI Missing | Low | Not Started | 1-2 days |
| Deployment Runbook Missing | Low | Not Started | 0.5 days |

---

*Concerns audit: 2026-04-04*
