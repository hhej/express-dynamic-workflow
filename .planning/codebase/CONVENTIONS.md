# Coding Conventions

**Analysis Date:** 2026-04-04

## Project Status

This is a project scaffold with architectural vision documented in `/docs/architecture.md` and README. Implementation is in early stage with directory structure and `__init__.py` files in place. Conventions below represent intended patterns for this codebase based on the stated tech stack (Python/FastAPI backend + Next.js/React frontend) and project requirements.

## Language-Specific Conventions

### Python Backend

**Location:** `backend/`

**Directory Structure:**
- `backend/agent/` — LangGraph orchestrator and multi-agent nodes
- `backend/agent/nodes/` — Individual agent implementations (Planner, Fuel Agent, Route Agent, Pricing Agent)
- `backend/agent/tools/` — Tool definitions (fetch_fuel_price, calculate_route, lookup_rate, calculate_surcharge, search_fuel_news)
- `backend/agent/prompts/` — Prompt templates for LLM calls
- `backend/api/` — FastAPI application, endpoints, request/response models
- `backend/evaluation/` — Evaluation and testing utilities

### TypeScript/JavaScript Frontend

**Location:** `frontend/`

**Expected Structure:**
- `frontend/app/` — Next.js 15 app directory (pages, layouts)
- `frontend/components/` — React components
- `frontend/hooks/` — Custom React hooks
- `frontend/lib/` — Utilities and helpers
- `frontend/api/` — Client-side API calls/services

## Naming Patterns

### Python Files and Functions

**Files:**
- Module files: `snake_case.py` (e.g., `fetch_fuel_prices.py`, `agent_state.py`)
- Test files: `test_<module>.py` (co-located with source or in `tests/` directory)

**Functions:**
- Functions and methods: `snake_case()` (e.g., `fetch_fuel_price()`, `calculate_surcharge()`)
- Private functions: Prefix with `_` (e.g., `_validate_input()`)
- Class methods following Python conventions (lowercase)

**Classes:**
- Classes: `PascalCase` (e.g., `AgentState`, `FuelAgent`, `PricingAgent`)
- Dataclass/TypedDict: `PascalCase` (e.g., `FuelData`, `RouteData`, `SurchargeResult`)

**Variables:**
- Variables: `snake_case` (e.g., `fuel_data`, `base_rate`, `traffic_severity`)
- Constants: `UPPER_CASE` (e.g., `BASELINE_DIESEL_PRICE`, `MAX_SURCHARGE_CAP`)
- Agent/node names in state: lowercase with underscores (e.g., `fetch_fuel`, `fetch_route`, `calculate_price`)

### TypeScript/JavaScript Files and Components

**Files:**
- Component files: `PascalCase.tsx` (e.g., `ChatInterface.tsx`, `SurchargeChart.tsx`)
- Hook files: `use<HookName>.ts` (e.g., `useFetchConversation.ts`)
- Utility files: `camelCase.ts` (e.g., `apiClient.ts`, `formatters.ts`)
- Type definition files: `types.ts` or `<domain>.types.ts` (e.g., `api.types.ts`, `agent.types.ts`)

**Functions:**
- Functions: `camelCase()` (e.g., `formatSurcharge()`, `parseAgentResponse()`)
- React hooks: `use<PascalCase>()` (e.g., `useChat()`, `useFeedback()`)

**Variables:**
- Variables: `camelCase` (e.g., `currentFuelPrice`, `surchargeAmount`, `isLoading`)
- React state: `camelCase` for state and setter names (e.g., `const [isLoading, setIsLoading]`)

**Types:**
- Types/Interfaces: `PascalCase` (e.g., `AgentMessage`, `SurchargeResponse`, `ChatState`)
- Type files: `*.types.ts` or interfaces inline near usage

## Code Style

### Python

**Formatting:**
- Follow **PEP 8** standard
- Line length: 88 characters (Black formatter default)
- Use `black` for automatic formatting if available
- Use `ruff` for linting (modern, fast replacement for flake8/pylint)

**Import Organization:**
```python
# 1. Standard library imports
import json
import sqlite3
from typing import TypedDict, Optional, Dict
from dataclasses import dataclass

# 2. Third-party imports
from fastapi import FastAPI, APIRouter
from langgraph.graph import StateGraph
from pydantic import BaseModel, Field

# 3. Local imports
from backend.agent.nodes import planner_node, fuel_agent_node
from backend.api.models import ChatRequest, ChatResponse
```

**Error Handling:**
- Use specific exception types (not bare `except:`)
- Define custom exceptions in a `exceptions.py` file at the package level
- Include context in error messages with relevant data (e.g., "Failed to fetch fuel price for region: central")

Example:
```python
class FuelPriceFetchError(Exception):
    """Raised when fuel price API call fails."""
    pass

try:
    price = fetch_fuel_price(region="central")
except FuelPriceFetchError as e:
    logger.error(f"Fuel fetch failed: {e}, falling back to CSV")
    price = load_latest_price_from_csv()
```

**Type Hints:**
- Use type hints for all function signatures
- Use `TypedDict` for dictionary-based state structures (e.g., `AgentState`)
- Use `Optional[]` or `|` (Python 3.10+) for optional values

### TypeScript/JavaScript

**Formatting:**
- Use **Prettier** with consistent settings (`.prettierrc`)
- Line length: 80-100 characters (project standard to be defined)
- Configure ESLint with `@next/next` and React plugin

**Import Organization:**
```typescript
// 1. React and external libraries
import React, { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';

// 2. Third-party UI/utility libraries
import clsx from 'clsx';

// 3. Application imports (organized by layer)
import { apiClient } from '@/lib/api';
import { AgentMessage, SurchargeResponse } from '@/types/agent.types';
import ChatWindow from '@/components/ChatWindow';
```

**Error Handling:**
- Use try/catch with proper error typing
- Log errors to console in development, to observability in production
- Provide user-friendly error messages

Example:
```typescript
try {
  const response = await apiClient.post('/api/chat', payload);
} catch (error) {
  if (error instanceof APIError) {
    showToast(`Error: ${error.message}`, 'error');
  } else {
    showToast('An unexpected error occurred', 'error');
  }
  logger.error('Chat request failed', error);
}
```

## Import Path Aliases

### Python Backend
- No aliases required; use relative imports for same-package modules
- Use absolute imports for different packages: `from backend.agent.nodes import ...`

### TypeScript Frontend
- Configure `jsconfig.json` or `tsconfig.json` with path aliases:
  ```json
  {
    "compilerOptions": {
      "baseUrl": ".",
      "paths": {
        "@/*": ["./*"],
        "@/components/*": ["./components/*"],
        "@/lib/*": ["./lib/*"],
        "@/types/*": ["./types/*"]
      }
    }
  }
  ```
- Use `@/` prefix for absolute imports within the app

## Comments and Documentation

### Python

**When to Comment:**
- Complex algorithm logic (especially surcharge calculation with traffic adjustments)
- Non-obvious LangGraph routing decisions
- Fallback mechanisms and error recovery paths
- Assumptions about data formats or external API contracts

**Docstrings:**
- Use Google-style docstrings for all public functions/classes
- Include Args, Returns, Raises sections

Example:
```python
def calculate_surcharge(
    base_rate: float,
    fuel_delta_pct: float,
    shipping_type: str,
    traffic_severity: int = 0,
) -> dict:
    """Calculate surcharge percentage and amount based on fuel and traffic.
    
    Args:
        base_rate: Base shipping rate in THB
        fuel_delta_pct: Fuel price change as percentage (e.g., 0.1 for +10%)
        shipping_type: One of 'bounce', 'retail_standard', 'retail_fast'
        traffic_severity: Traffic level 1-5 (Bounce only)
    
    Returns:
        Dict with keys: surcharge_pct, surcharge_amount, total, capped (bool)
    
    Raises:
        ValueError: If shipping_type is invalid or traffic_severity out of range
    """
```

### TypeScript/JavaScript

**JSDoc:**
- Use JSDoc for public functions and component prop types
- Describe purpose, params, and return type

Example:
```typescript
/**
 * Format surcharge percentage for display
 * @param surcharge - Surcharge as decimal (e.g., 0.12 for 12%)
 * @returns Formatted string (e.g., "+12.0%")
 */
export function formatSurcharge(surcharge: number): string {
  return `${surcharge >= 0 ? '+' : ''}${(surcharge * 100).toFixed(1)}%`;
}

interface ChatMessageProps {
  /** Message content from agent or user */
  content: string;
  /** 'user' | 'agent' | 'system' */
  role: 'user' | 'agent' | 'system';
  /** Optional tool calls that were made */
  toolCalls?: ToolCall[];
}
```

## Agent and Node Conventions

### LangGraph Agent Nodes

**File Structure:**
- Each node implementation in `backend/agent/nodes/<node_name>.py`
- Exports a single callable or function matching the node's name
- Uses type hints with `AgentState` from `backend/agent/state.py`

Example file: `backend/agent/nodes/planner_node.py`
```python
from backend.agent.state import AgentState

async def planner_node(state: AgentState) -> dict:
    """Route user message to appropriate agent(s)."""
    # Implementation
    return {"next_step": "fetch_fuel", "reasoning_trace": [...]}
```

**Naming:**
- Node names: `<agent_name>_node` (e.g., `fuel_agent_node`, `pricing_agent_node`)
- Next step routing values: lowercase with underscores (e.g., `fetch_fuel`, `fetch_route`, `calculate_price`, `respond`)

### Tool Definitions

**Location:** `backend/agent/tools/<tool_name>.py`

**Structure:**
```python
from langchain.tools import tool

@tool
def fetch_fuel_price(fuel_type: str, region: str) -> dict:
    """Fetch current fuel price from EPPO or PTT API.
    
    Args:
        fuel_type: e.g. 'diesel_b7', 'gasohol_95'
        region: e.g. 'central'
    
    Returns:
        {'price': float, 'date': str, 'unit': 'THB/L', 'source': str}
    """
```

## State Management Conventions

### AgentState (LangGraph)

**Location:** `backend/agent/state.py`

**Structure:**
- Use `TypedDict` for clarity and type safety
- Include comment describing each field
- Keys are `snake_case`

Example:
```python
from typing import TypedDict

class AgentState(TypedDict):
    """State shared across LangGraph nodes."""
    messages: list  # Conversation history
    fuel_data: dict | None  # {price, date, source, baseline, delta_pct}
    route_data: dict | None  # {distance_km, duration_min, traffic_severity, zone}
    shipping_type: str | None  # 'bounce' | 'retail_standard' | 'retail_fast'
    weight_kg: float | None
    surcharge_result: dict | None  # {base_rate, surcharge_pct, amount, total, capped}
    next_step: str  # Router field for conditional edges
```

### Frontend Component State

**React Hooks Pattern:**
```typescript
// Co-locate state at component level
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [isLoading, setIsLoading] = useState(false);
const [surchargeData, setSurchargeData] = useState<SurchargeResponse | null>(null);

// Extract complex state logic into custom hooks
const { data: fuelPrices, isLoading: isLoadingPrices } = useFetchFuelPrices();
```

## API Design Conventions

### FastAPI Endpoints

**Request/Response Models:**
- Use Pydantic `BaseModel` for all request/response bodies
- Define in `backend/api/models.py` or `backend/api/schemas.py`
- Use descriptive field names with type hints

Example:
```python
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    """User message for chat endpoint."""
    thread_id: str = Field(..., description="Conversation thread UUID")
    message: str = Field(..., min_length=1, max_length=2000)
    
class ChatResponse(BaseModel):
    """Agent response with reasoning trace."""
    response: str
    reasoning_trace: list[dict]
    surcharge_result: dict | None = None
```

**Endpoint Naming:**
- Resource-based (e.g., `/api/chat`, `/api/conversations`, `/api/feedback`)
- Use HTTP methods correctly (POST for mutations, GET for queries)

### Frontend API Client

**Location:** `frontend/lib/api.ts` or `frontend/lib/apiClient.ts`

**Pattern:**
```typescript
export const apiClient = {
  async postChat(threadId: string, message: string): Promise<ChatResponse> {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId, message }),
    });
    
    if (!response.ok) throw new APIError(`API error: ${response.status}`);
    return response.json();
  },
};
```

## Constants and Configuration

### Python

**Define in:** `backend/config.py` or use environment variables

```python
import os
from dataclasses import dataclass

@dataclass
class Config:
    """Application configuration from environment."""
    BASELINE_DIESEL_PRICE: float = float(os.getenv('BASELINE_DIESEL_PRICE', '29.94'))
    SURCHARGE_CAP: float = float(os.getenv('SURCHARGE_CAP', '0.15'))
    SURCHARGE_FLOOR: float = float(os.getenv('SURCHARGE_FLOOR', '-0.05'))
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', 'data/express.db')
```

### TypeScript

**Define in:** `frontend/lib/constants.ts` or `frontend/config.ts`

```typescript
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export const SHIPPING_TYPES = {
  BOUNCE: 'bounce',
  RETAIL_STANDARD: 'retail_standard',
  RETAIL_FAST: 'retail_fast',
} as const;

export const TRAFFIC_LEVELS = {
  LIGHT: 1,
  MODERATE: 2,
  HEAVY: 3,
  CONGESTED: 4,
  SEVERE: 5,
} as const;
```

## Logging Conventions

### Python

**Framework:** Standard library `logging` module

**Pattern:**
```python
import logging

logger = logging.getLogger(__name__)

logger.debug("Checking memory for fuel data")
logger.info("Fuel price fetched: 32.50 THB/L")
logger.warning("Fuel price cap applied: surcharge reduced from 18% to 15%")
logger.error(f"Failed to calculate surcharge: {error}", exc_info=True)
```

**When to Log:**
- Tool invocations (start and result)
- Cache hits/misses
- Fallback mechanisms
- Errors with full context

### TypeScript/React

**Pattern:**
```typescript
console.log('[AgentResponse] Surcharge calculated:', result);
logger.warn('[Chat] Message send failed, retrying...', { retry: 1 });
```

## File Organization Summary

**Python Backend:**
- Agent logic: `backend/agent/nodes/*.py`
- Tools: `backend/agent/tools/*.py`
- Prompts: `backend/agent/prompts/*.py`
- API endpoints: `backend/api/routes/*.py`
- Models: `backend/api/models.py`
- State: `backend/agent/state.py`
- Config: `backend/config.py`
- Tests: `backend/tests/test_*.py`

**TypeScript Frontend:**
- Pages: `frontend/app/*.tsx`
- Components: `frontend/components/*.tsx`
- Hooks: `frontend/hooks/use*.ts`
- API: `frontend/lib/api.ts`
- Types: `frontend/types/*.ts`
- Utils: `frontend/lib/*.ts`
- Tests: `frontend/__tests__/`, `frontend/components/*.test.tsx`

---

*Convention analysis: 2026-04-04*
