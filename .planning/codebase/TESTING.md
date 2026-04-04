# Testing Patterns

**Analysis Date:** 2026-04-04

## Project Status

This is a project scaffold with testing infrastructure not yet implemented. This document outlines the recommended testing approach based on the project's tech stack (Python/FastAPI backend + Next.js/React frontend), LangGraph agent complexity, and observability requirements.

## Backend Testing (Python)

### Test Framework Setup

**Recommended Stack:**
- **Test Runner:** `pytest` (industry standard, powerful fixtures, parameterization)
- **Async Support:** `pytest-asyncio` (for async agent nodes)
- **Mocking:** `unittest.mock` (built-in) or `pytest-mock` (pytest plugin)
- **HTTP Client Testing:** `httpx` async client with test fixtures
- **Database Testing:** `pytest-sqlite` or in-memory SQLite fixtures

**Run Commands:**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=html

# Watch mode (with pytest-watch)
ptw

# Run specific test file
pytest backend/tests/test_fuel_agent.py

# Run tests matching pattern
pytest -k "surcharge" -v
```

**Configuration File:** `backend/pytest.ini` or `pyproject.toml`
```ini
[pytest]
asyncio_mode = auto
testpaths = backend/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: unit tests
    integration: integration tests
    agent: agent/LangGraph tests
```

### Test File Organization

**Location:** `backend/tests/`

**Structure:**
```
backend/tests/
├── __init__.py
├── conftest.py                      # Shared fixtures
├── test_agent_state.py              # Agent state tests
├── test_fuel_agent.py               # Fuel agent tests
├── test_route_agent.py              # Route agent tests
├── test_pricing_agent.py            # Pricing agent tests
├── test_planner_node.py             # Planner routing tests
├── tools/
│   ├── test_fetch_fuel_price.py     # Fuel price tool tests
│   ├── test_calculate_route.py      # Route calculation tests
│   ├── test_lookup_rate.py          # Rate lookup tests
│   └── test_calculate_surcharge.py  # Surcharge calculation tests
├── api/
│   ├── test_chat_endpoint.py        # Chat endpoint tests
│   ├── test_conversations.py        # Conversation management tests
│   └── test_feedback.py             # Feedback endpoint tests
└── fixtures/
    ├── mock_fuel_data.py            # Fuel data fixtures
    ├── mock_route_data.py           # Route data fixtures
    └── mock_agent_state.py          # State fixtures
```

### Fixture Patterns

**Location:** `backend/tests/conftest.py`

**Example Fixtures:**
```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.agent.state import AgentState

@pytest.fixture
def agent_state() -> AgentState:
    """Create a fresh AgentState for testing."""
    return {
        "messages": [],
        "fuel_data": None,
        "route_data": None,
        "shipping_type": None,
        "weight_kg": None,
        "surcharge_result": None,
        "reasoning_trace": [],
        "next_step": "respond",
    }

@pytest.fixture
def mock_fuel_data() -> dict:
    """Mock fuel price response."""
    return {
        "price": 32.50,
        "date": "2026-04-04",
        "source": "EPPO",
        "unit": "THB/L",
        "baseline": 29.94,
        "delta_pct": 0.0857,
    }

@pytest.fixture
def mock_route_data() -> dict:
    """Mock route calculation response."""
    return {
        "distance_km": 25.5,
        "duration_min": 45,
        "traffic_severity": 3,
        "zone": "central-1",
    }

@pytest.fixture
async def mock_fuel_price_tool() -> AsyncMock:
    """Mock the fetch_fuel_price tool."""
    tool = AsyncMock()
    tool.return_value = {
        "price": 32.50,
        "date": "2026-04-04",
        "source": "EPPO",
        "unit": "THB/L",
    }
    return tool

@pytest.fixture
def sqlite_db():
    """Create an in-memory SQLite database for testing."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    # Initialize schema
    conn.execute("""
        CREATE TABLE rates (
            shipping_type TEXT,
            zone TEXT,
            weight_min REAL,
            weight_max REAL,
            base_rate REAL
        )
    """)
    yield conn
    conn.close()
```

### Test Structure and Patterns

**Unit Test Example:**
```python
# backend/tests/tools/test_calculate_surcharge.py
import pytest
from backend.agent.tools.calculate_surcharge import calculate_surcharge

class TestCalculateSurcharge:
    """Tests for surcharge calculation logic."""
    
    def test_bounce_surcharge_with_positive_fuel_delta(self):
        """Bounce shipping fully exposed to fuel costs."""
        result = calculate_surcharge(
            base_rate=100.0,
            fuel_delta_pct=0.10,  # +10% fuel
            shipping_type="bounce",
            traffic_severity=0,
        )
        assert result["surcharge_pct"] == 0.10
        assert result["surcharge_amount"] == 10.0
        assert result["total"] == 110.0
        assert result["capped"] is False
    
    def test_retail_fast_surcharge_partial_exposure(self):
        """Retail Fast has 0.8x fuel sensitivity."""
        result = calculate_surcharge(
            base_rate=100.0,
            fuel_delta_pct=0.10,
            shipping_type="retail_fast",
            traffic_severity=0,
        )
        assert result["surcharge_pct"] == pytest.approx(0.08)
        assert result["surcharge_amount"] == pytest.approx(8.0)
    
    def test_bounce_traffic_adjustment(self):
        """Bounce surcharge increases with traffic severity."""
        result = calculate_surcharge(
            base_rate=100.0,
            fuel_delta_pct=0.10,
            shipping_type="bounce",
            traffic_severity=5,  # Maximum severity
        )
        # 10% base + (5 * 2%) traffic = 20% surcharge
        assert result["surcharge_pct"] == pytest.approx(0.20)
    
    @pytest.mark.parametrize("shipping_type,expected_multiplier", [
        ("bounce", 1.0),
        ("retail_fast", 0.8),
        ("retail_standard", 0.5),
    ])
    def test_shipping_type_multipliers(self, shipping_type, expected_multiplier):
        """Verify multipliers for each shipping type."""
        result = calculate_surcharge(
            base_rate=100.0,
            fuel_delta_pct=0.10,
            shipping_type=shipping_type,
            traffic_severity=0,
        )
        assert result["surcharge_pct"] == pytest.approx(0.10 * expected_multiplier)
    
    def test_surcharge_cap_applied(self):
        """Surcharge capped at 15% maximum."""
        result = calculate_surcharge(
            base_rate=100.0,
            fuel_delta_pct=0.30,  # +30% fuel (would exceed cap)
            shipping_type="bounce",
            traffic_severity=0,
        )
        assert result["surcharge_pct"] == 0.15
        assert result["capped"] is True
    
    def test_surcharge_floor_applied(self):
        """Surcharge floored at -5% discount."""
        result = calculate_surcharge(
            base_rate=100.0,
            fuel_delta_pct=-0.20,  # -20% fuel (would exceed floor)
            shipping_type="bounce",
            traffic_severity=0,
        )
        assert result["surcharge_pct"] == -0.05
        assert result["capped"] is True
    
    def test_invalid_shipping_type_raises_error(self):
        """Invalid shipping_type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid shipping_type"):
            calculate_surcharge(
                base_rate=100.0,
                fuel_delta_pct=0.10,
                shipping_type="invalid_type",
                traffic_severity=0,
            )
```

### Agent/LangGraph Testing

**Pattern for Testing Nodes:**
```python
# backend/tests/test_fuel_agent.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.agent.nodes.fuel_agent import fuel_agent_node
from backend.agent.state import AgentState

@pytest.mark.asyncio
class TestFuelAgent:
    """Tests for the Fuel Agent node."""
    
    async def test_fuel_agent_fetches_price(self, agent_state, mock_fuel_data):
        """Fuel agent successfully fetches current price."""
        with patch('backend.agent.nodes.fuel_agent.fetch_fuel_price') as mock_tool:
            mock_tool.return_value = mock_fuel_data
            
            # Add user message to state
            agent_state["messages"] = [
                {"role": "user", "content": "What's the current diesel price?"}
            ]
            
            result = await fuel_agent_node(agent_state)
            
            assert result["fuel_data"] is not None
            assert result["fuel_data"]["price"] == 32.50
            assert len(result["reasoning_trace"]) > 0
    
    async def test_fuel_agent_uses_cached_data(self, agent_state, mock_fuel_data):
        """Fuel agent skips fetch if data is recent."""
        import time
        recent_timestamp = time.time() - 600  # 10 minutes old
        
        agent_state["fuel_data"] = {
            **mock_fuel_data,
            "timestamp": recent_timestamp,
        }
        
        with patch('backend.agent.nodes.fuel_agent.fetch_fuel_price') as mock_tool:
            result = await fuel_agent_node(agent_state)
            
            # Tool should not be called
            mock_tool.assert_not_called()
            # Cached data should remain
            assert result["fuel_data"]["price"] == 32.50
    
    async def test_fuel_agent_fallback_on_error(self, agent_state):
        """Fuel agent falls back to CSV if API fails."""
        with patch('backend.agent.nodes.fuel_agent.fetch_fuel_price') as mock_tool:
            mock_tool.side_effect = Exception("API error")
            with patch('backend.agent.nodes.fuel_agent.load_latest_price_from_csv') as mock_csv:
                mock_csv.return_value = {
                    "price": 31.50,
                    "source": "CSV_FALLBACK",
                }
                
                result = await fuel_agent_node(agent_state)
                
                assert result["fuel_data"]["source"] == "CSV_FALLBACK"
                assert "error" in result["reasoning_trace"][-1]
```

### Mocking Patterns

**What to Mock:**
- External API calls (fuel price, Google Maps, Tavily)
- Database queries (for unit tests; use real SQLite in integration tests)
- LLM calls (use fixed responses for deterministic tests)
- Tool invocations (for isolation testing)

**What NOT to Mock:**
- Core business logic (surcharge calculation)
- Agent state transitions
- Data structure transformations
- Config/constants

**Example Mocking Strategy:**
```python
from unittest.mock import patch, AsyncMock
from backend.agent.tools.fetch_fuel_price import fetch_fuel_price

@patch('backend.agent.tools.fetch_fuel_price.requests.get')
async def test_fetch_fuel_price_api_call(mock_get):
    """Mock HTTP request, test tool wrapper logic."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"price": 32.50, "unit": "THB/L"}
    mock_response.status_code = 200
    mock_get.return_value = mock_response
    
    result = await fetch_fuel_price("diesel_b7", "central")
    
    assert result["price"] == 32.50
    mock_get.assert_called_once_with(
        "https://api.eppo.go.th/prices",
        params={"fuel_type": "diesel_b7", "region": "central"}
    )
```

### Integration Tests

**Pattern:**
```python
# backend/tests/test_agent_integration.py
import pytest
from backend.agent.graph import create_agent_graph
from backend.agent.state import AgentState

@pytest.mark.integration
@pytest.mark.asyncio
class TestAgentIntegration:
    """Integration tests with real (or mostly real) components."""
    
    async def test_full_surcharge_query_flow(self, sqlite_db):
        """Test complete flow: query → agents → surcharge calculation."""
        graph = create_agent_graph(db=sqlite_db)
        
        initial_state: AgentState = {
            "messages": [
                {"role": "user", "content": 
                 "What's the fuel surcharge for a Bounce shipment, 200kg, from Bangkok to Nonthaburi?"}
            ],
            "fuel_data": None,
            "route_data": None,
            "shipping_type": None,
            "weight_kg": None,
            "surcharge_result": None,
            "reasoning_trace": [],
            "next_step": "planner",
        }
        
        # Run the agent graph
        final_state = await graph.ainvoke(initial_state)
        
        # Verify complete result
        assert final_state["surcharge_result"] is not None
        assert "surcharge_pct" in final_state["surcharge_result"]
        assert final_state["next_step"] == "respond"
        assert len(final_state["reasoning_trace"]) > 0
        
        # Verify all agents were invoked
        agent_names = [step["agent"] for step in final_state["reasoning_trace"]]
        assert "planner" in agent_names
        assert "fuel_agent" in agent_names or "cached_fuel_data" in agent_names
```

### Coverage Requirements

**Target:** 80%+ overall coverage

**Priority Areas (aim for 100%):**
- `backend/agent/tools/calculate_surcharge.py` — Critical business logic
- `backend/agent/state.py` — State management
- `backend/api/models.py` — Request validation

**Minimum Coverage:**
- Agent nodes: 80%+
- Tool implementations: 85%+
- API endpoints: 75%+

**View Coverage:**
```bash
pytest --cov=backend --cov-report=html
# Open htmlcov/index.html in browser
```

---

## Frontend Testing (TypeScript/React)

### Test Framework Setup

**Recommended Stack:**
- **Test Runner:** `Vitest` (Vite-native, faster than Jest) or `Jest` (more ecosystem support)
- **Component Testing:** `@testing-library/react` (user-centric testing)
- **E2E Testing:** `Playwright` or `Cypress` (agent interaction flows)
- **Mocking:** `MSW` (Mock Service Worker) for API mocking

**Run Commands:**
```bash
# Run all tests
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage

# E2E tests
npm run test:e2e
```

**Configuration:** `frontend/vitest.config.ts` or `jest.config.js`
```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['node_modules/', 'tests/'],
    },
  },
});
```

### Test File Organization

**Location:** `frontend/__tests__/` or co-located `*.test.tsx`

**Structure:**
```
frontend/
├── components/
│   ├── ChatWindow.tsx
│   ├── ChatWindow.test.tsx          # Component unit tests
│   ├── SurchargeChart.tsx
│   └── SurchargeChart.test.tsx
├── hooks/
│   ├── useFetchConversation.ts
│   └── useFetchConversation.test.ts
├── __tests__/
│   ├── setup.ts                      # Vitest/Jest setup
│   ├── mocks/
│   │   ├── handlers.ts               # MSW handlers
│   │   └── server.ts                 # MSW server setup
│   ├── integration/
│   │   └── chat-flow.test.tsx        # End-to-end chat flow
│   └── unit/
│       ├── formatters.test.ts
│       └── api-client.test.ts
└── lib/
    └── api.test.ts
```

### Fixture and Mock Patterns

**API Mocking with MSW:**
```typescript
// frontend/__tests__/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('/api/chat', async ({ request }) => {
    const { message } = await request.json();
    
    return HttpResponse.json({
      response: 'Fuel surcharge for Bounce shipment: +12.0%',
      reasoning_trace: [
        { agent: 'planner', decision: 'fetch_fuel' },
        { agent: 'fuel_agent', fuel_price: 32.50 },
      ],
      surcharge_result: { surcharge_pct: 0.12 },
    });
  }),
];

// frontend/__tests__/mocks/server.ts
import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);

// frontend/__tests__/setup.ts
import { server } from './mocks/server';

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Component Testing Pattern

**Example:**
```typescript
// frontend/components/ChatWindow.test.tsx
import { render, screen, userEvent } from '@testing-library/react';
import { ChatWindow } from './ChatWindow';

describe('ChatWindow', () => {
  it('sends message and displays response', async () => {
    const user = userEvent.setup();
    render(<ChatWindow threadId="test-123" />);
    
    const input = screen.getByRole('textbox', { name: /message/i });
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    await user.type(input, 'What is the fuel surcharge?');
    await user.click(sendButton);
    
    // Wait for response
    const response = await screen.findByText(/fuel surcharge/i);
    expect(response).toBeInTheDocument();
  });
  
  it('displays loading state while fetching', async () => {
    const user = userEvent.setup();
    render(<ChatWindow threadId="test-123" />);
    
    const input = screen.getByRole('textbox');
    const sendButton = screen.getByRole('button', { name: /send/i });
    
    await user.type(input, 'Query');
    await user.click(sendButton);
    
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
  
  it('displays error message on API failure', async () => {
    server.use(
      http.post('/api/chat', () => 
        HttpResponse.error()
      )
    );
    
    const user = userEvent.setup();
    render(<ChatWindow threadId="test-123" />);
    
    await user.type(screen.getByRole('textbox'), 'Query');
    await user.click(screen.getByRole('button', { name: /send/i }));
    
    const error = await screen.findByText(/error/i);
    expect(error).toBeInTheDocument();
  });
});
```

### Hook Testing Pattern

**Example:**
```typescript
// frontend/hooks/useFetchConversation.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { useFetchConversation } from './useFetchConversation';

describe('useFetchConversation', () => {
  it('fetches conversation on mount', async () => {
    const { result } = renderHook(() => useFetchConversation('thread-123'));
    
    expect(result.current.isLoading).toBe(true);
    
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    
    expect(result.current.messages).toHaveLength(3);
  });
  
  it('refetches when threadId changes', async () => {
    const { result, rerender } = renderHook(
      ({ threadId }) => useFetchConversation(threadId),
      { initialProps: { threadId: 'thread-1' } }
    );
    
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    
    rerender({ threadId: 'thread-2' });
    
    expect(result.current.isLoading).toBe(true);
  });
});
```

### E2E Testing Pattern

**Example with Playwright:**
```typescript
// frontend/tests/e2e/chat-flow.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Chat Flow', () => {
  test('complete surcharge query flow', async ({ page }) => {
    await page.goto('http://localhost:3000');
    
    // Type query
    const input = page.getByRole('textbox', { name: /message/i });
    await input.fill('What is the fuel surcharge for Bounce, 200kg, Bangkok to Nonthaburi?');
    
    // Send message
    await page.getByRole('button', { name: /send/i }).click();
    
    // Wait for response
    await expect(page.getByText(/surcharge/i)).toBeVisible({ timeout: 10000 });
    
    // Verify surcharge is displayed
    const surchargeValue = page.locator('[data-testid="surcharge-value"]');
    await expect(surchargeValue).toHaveText(/\d+\.\d+%/);
    
    // Verify reasoning trace is visible
    const tracePanel = page.locator('[data-testid="trace-panel"]');
    await expect(tracePanel).toBeVisible();
  });
});
```

### Coverage Requirements

**Target:** 70%+ overall coverage

**Priority Areas:**
- `components/ChatWindow.tsx` — Main user interaction (90%+)
- `lib/apiClient.ts` — API communication (85%+)
- `hooks/useFetchConversation.ts` — State management (80%+)

**View Coverage:**
```bash
npm run test:coverage
# Open coverage/index.html in browser
```

---

## Observability and Test Evaluation

### Automated Evaluation (Langfuse Integration)

**Backend Metric:** Surcharge formula accuracy

```python
# backend/evaluation/test_surcharge_accuracy.py
from backend.agent.tools.calculate_surcharge import calculate_surcharge
from langfuse.decorators import langfuse_context

@langfuse_context.observe()
def evaluate_surcharge(fuel_delta: float, shipping_type: str) -> dict:
    """Auto-evaluate surcharge calculation."""
    result = calculate_surcharge(
        base_rate=100.0,
        fuel_delta_pct=fuel_delta,
        shipping_type=shipping_type,
        traffic_severity=0,
    )
    
    # Independent calculation for verification
    expected = independent_calculation(fuel_delta, shipping_type)
    
    is_correct = abs(result["surcharge_pct"] - expected) < 0.001
    
    langfuse_context.score_current_observation(
        name="surcharge_accuracy",
        value=1.0 if is_correct else 0.0,
        data_type="boolean",
    )
    
    return result
```

### Manual Test Evaluation

**User Feedback Loop:**
1. User tests query in chat UI
2. Clicks thumbs up/down on response
3. Feedback sent to backend → Langfuse
4. Scores aggregated in Langfuse dashboard

### Test Documentation

**Mark tests with metadata:**
```python
@pytest.mark.unit
@pytest.mark.agent
def test_planner_routing():
    """Test planner correctly routes to fuel agent."""
    
@pytest.mark.integration
@pytest.mark.slow
async def test_full_agent_flow():
    """Test end-to-end agent graph execution."""
```

---

## Continuous Integration Recommendations

**Pre-commit Checks:**
- `pytest` with coverage threshold (80%)
- `black` for Python formatting
- `ruff check` for linting
- `prettier` for TypeScript/React
- `eslint` for frontend linting

**CI Pipeline (GitHub Actions):**
```yaml
- name: Backend Tests
  run: |
    cd backend
    pytest --cov=. --cov-fail-under=80
    
- name: Frontend Tests
  run: |
    cd frontend
    npm run test:coverage
```

---

*Testing analysis: 2026-04-04*
