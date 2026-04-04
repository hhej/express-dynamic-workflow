# Express Dynamic Surcharge Orchestrator

An Agentic AI system that dynamically calculates fuel surcharges for Express logistics operations in Thailand's Central Region, based on real-time oil prices, route data, and shipping type.

**Course**: MADT7204 — Vibe Coding Project  
**Scope**: Bangkok + Central Region (Nonthaburi, Pathum Thani, Samut Prakan, Nakhon Pathom, Samut Sakhon, Ayutthaya)

---

## Team Members

| Role | Student ID | Name |
|------|-----------|------|
| **Tech Lead** | 6810424009 | Panjapol Ampornratana |
| Management Member | 6810424004 | Jirapa Panich |
| Management Member | 6810424008 | Phanitphan Eaimnon |
| Management Member | 6810424012 | Tanakrid Burutchat |
| Management Member | 6810424020 | Phatthakan Phatthanuwat |

---

## Problem Statement

Oil prices in Thailand are at historic highs. Bangkok-based logistics companies face significant margin erosion because their shipping costs rely on **static pricing models** that cannot keep pace with daily fuel fluctuations.

Express operates two customer segments with three shipping types:

- **Bounce (B2B)**: Weight and distance-based pricing for bulk shipments. Directly exposed to fuel cost changes.
- **Retail Standard (B2C)**: Flat-rate consumer parcels with 3-5 day delivery. Partially absorbs fuel cost increases.
- **Retail Fast (B2C)**: Premium same/next-day delivery. High fuel exposure due to dedicated routes.

Every spike in diesel prices represents a direct loss in profitability because surcharges cannot be adjusted in real-time. Manual pricing reviews happen too slowly to respond to daily fuel market movements.

**This agent solves that problem** by automatically monitoring fuel prices, analyzing delivery routes, and recommending optimal surcharges — with full reasoning transparency for management oversight.

---

## Agent Design

### What the Agent Does

1. **Reasons over data** to compute surcharge recommendations — not just display prices
2. **Calls external tools dynamically** (fuel price API, maps, rate database, search) based on user queries
3. **Handles follow-up questions** and what-if scenarios without re-programming
4. **Orchestrates sub-agents** — a planner delegates to specialized fuel, route, and pricing agents
5. **Shows its reasoning** — every tool call and decision is visible in the UI trace panel

### Architecture

The system uses a **LangGraph multi-agent graph** with four specialist nodes:

| Agent | Role | Tools Used |
|-------|------|-----------|
| **Planner** | Understands user intent, routes to specialists, checks memory | None (pure reasoning) |
| **Fuel Agent** | Retrieves current fuel prices and trends | `fetch_fuel_price`, `search_fuel_news` |
| **Route Agent** | Calculates delivery distance, traffic, and zone | `calculate_route` |
| **Pricing Agent** | Computes surcharge using rate tables and fuel data | `lookup_rate`, `calculate_surcharge` |

The planner checks conversation memory before invoking agents — if fuel data was fetched recently, it skips the Fuel Agent and routes directly to pricing. This makes follow-up questions fast and efficient.

See [docs/architecture.md](docs/architecture.md) for the full technical architecture including agent state, graph flow, and surcharge calculation logic.

---

## Data Sources

| Source | Type | What It Provides | Used By |
|--------|------|-----------------|---------|
| [EPPO](https://www.eppo.go.th/) (Dept. of Energy Business) | Public/Government | Daily diesel retail prices, Central Region | Fuel Agent |
| PTT Price Board | Live API/Scrape | Current fuel prices by type | Fuel Agent |
| Express Rate Table | Simulated | Base shipping rates for 3 types x 3 zones x weight tiers | Pricing Agent |
| Google Maps Directions API | Live API | Route distance + travel time + traffic | Route Agent |
| Tavily Search API | Live API | Fuel price news and market context | Fuel Agent |

### Data Storage

- **Historical fuel prices**: `data/raw/eppo_diesel_prices.csv` — downloaded via `data/scripts/fetch_fuel_prices.py`
- **Rate table**: `data/raw/express_rate_table.csv` — generated via `data/scripts/generate_rate_table.py` (assumptions documented in script)
- **Rate database**: `data/express.db` — SQLite, seeded from CSVs via `data/scripts/seed_database.py`
- **Conversation memory**: `data/checkpoints.db` — LangGraph SQLite checkpointer

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+
- API keys for: Google AI Studio (Gemini), Google Maps, Tavily, Langfuse

### 1. Clone the Repository

```bash
git clone <repo-url>
cd express-dynamic-workflow
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

### 4. Environment Variables

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 5. Seed the Database

```bash
cd data/scripts
python fetch_fuel_prices.py
python generate_rate_table.py
python seed_database.py
```

### 6. Run the Application

**Terminal 1 — Backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Example Queries

Try these in the chat interface:

- "What's the fuel surcharge for a Bounce shipment, 200kg, from Bangkok to Nonthaburi?"
- "What about Retail Fast for the same route?"
- "Compare surcharges for all three shipping types from Bangkok to Pathum Thani"
- "What if diesel goes up by 2 baht?"
- "What's the current diesel price trend?"

---

## Observability (Langfuse)

All agent traces are logged to [Langfuse](https://cloud.langfuse.com/) for monitoring and evaluation:

- **Trace view**: Full agent workflow per query (which agents ran, what tools were called)
- **Latency**: Which tool/agent is the bottleneck
- **Token usage**: Cost tracking per query
- **Evaluation scores**: Formula accuracy (auto-eval) + user feedback (manual)
- **User feedback**: Thumbs up/down from the UI, with categorized reasons for thumbs down

---

## Vibe-Coding Tools Used

| Tool | What It Was Used For |
|------|---------------------|
| Claude Code (CLI) | Project architecture design, code generation, debugging, documentation |
| GSD Framework | Project planning workflow — requirements, roadmap, phased execution, verification |
| Claude Code (IDE) | In-editor code assistance via VS Code extension |

---

## Known Limitations

- **Fuel price data**: EPPO data may have a 1-day lag; live PTT scraping depends on website availability
- **Route accuracy**: Google Maps traffic data is real-time but zone mapping is simplified to 3 zones
- **Rate table**: Simulated based on assumptions — not actual Express pricing
- **Surcharge caps**: Fixed at 15% max / -5% min — a production system would need configurable per-customer caps
- **LLM rate limits**: Gemini free tier allows 15 RPM — sufficient for demo but not production traffic
- **Central Region only**: Does not cover northern, southern, or northeastern Thailand

## Future Improvements

- Expand to all Thailand regions with region-specific fuel pricing
- Add per-customer surcharge cap configuration
- Integrate with actual Express pricing systems via API
- Add historical surcharge tracking and trend analysis
- Support for additional fuel types (LPG, NGV) for different vehicle fleets
- Automated daily surcharge report generation and email distribution
- RAG integration with fuel policy documents and government subsidy announcements
