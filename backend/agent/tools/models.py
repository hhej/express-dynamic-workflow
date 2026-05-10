"""Pydantic input/output models for all agent tools (TOOL-06)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

__all__ = [
    "SurchargeInput",
    "SurchargeResult",
    "FuelData",
    "RouteData",
    "RateResult",
    # Phase 5 additions
    "SearchInput",
    "SearchSource",
    "SearchResult",
]


class SurchargeInput(BaseModel):
    """Input for surcharge calculation tool.

    Args:
        base_rate: Base shipping rate in THB (must be > 0).
        current_diesel_price: Current diesel B7 price in THB/L (must be > 0).
        shipping_type: One of "bounce", "retail_standard", "retail_fast".
        traffic_severity: Traffic severity on a 1-5 scale (default 1).
    """

    base_rate: float = Field(gt=0, description="Base shipping rate in THB")
    current_diesel_price: float = Field(
        gt=0, description="Current diesel B7 price THB/L"
    )
    shipping_type: str = Field(
        description="bounce | retail_standard | retail_fast"
    )
    traffic_severity: int = Field(
        default=1, ge=1, le=5, description="Traffic 1-5 scale"
    )


class SurchargeResult(BaseModel):
    """Output from surcharge calculation.

    Args:
        surcharge_pct: Surcharge percentage (e.g., 0.05 = 5%).
        surcharge_amount: Surcharge amount in THB.
        total: Base rate + surcharge in THB.
        capped: Whether cap or floor was applied.
    """

    surcharge_pct: float = Field(
        description="Surcharge percentage (e.g., 0.05 = 5%)"
    )
    surcharge_amount: float = Field(description="Surcharge amount in THB")
    total: float = Field(description="Base rate + surcharge in THB")
    capped: bool = Field(description="Whether cap or floor was applied")


class FuelData(BaseModel):
    """Fuel price data from EPPO/PTT.

    Args:
        price: Current diesel B7 price in THB/L.
        date: Price date in YYYY-MM-DD format.
        unit: Price unit (default "THB/L").
        source: Data source identifier - eppo | ptt | eppo_live | eppo_cached_csv | hardcoded_baseline.
        baseline: Baseline diesel price for comparison.
        delta_pct: Percentage change from baseline.
    """

    price: float = Field(description="Current diesel B7 price in THB/L")
    date: str = Field(description="Price date YYYY-MM-DD")
    unit: str = Field(default="THB/L")
    source: str = Field(
        description=(
            "Data source identifier. Phase 1 values: 'eppo', 'ptt'. "
            "Phase 2 adds: 'eppo_live' (live scrape), 'eppo_cached_csv' "
            "(fallback to data/raw/eppo_diesel_prices.csv), "
            "'hardcoded_baseline' (final fallback to BASELINE_DIESEL_PRICE)."
        )
    )
    baseline: float = Field(
        description="Baseline diesel price for comparison"
    )
    delta_pct: float = Field(
        description="Percentage change from baseline"
    )


class RouteData(BaseModel):
    """Route calculation output.

    Args:
        origin: Origin location name or address.
        destination: Destination location name or address.
        distance_km: Route distance in kilometers.
        duration_min: Estimated travel duration in minutes.
        traffic_severity: Traffic severity on a 1-5 scale.
        zone: Zone identifier (central-1, central-2, or central-3).
        origin_hub_id: Phase 999.9 D-04 origin hub identifier
            (e.g., 'hq-lat-krabang', 'branch-bang-na'). Optional /
            None permitted for tests + cached pre-999.9 entries;
            production code always supplies a hub_id (calculate_route
            fills it from its argument).
    """

    origin: str
    destination: str
    distance_km: float
    duration_min: int
    traffic_severity: int = Field(ge=1, le=5)
    zone: str = Field(
        description="central-1, central-2, or central-3"
    )

    # Phase 999.9 D-04: hub_id used for the route. None permitted for
    # tests + cached pre-999.9 entries; production code always supplies
    # a hub_id (calculate_route fills it from its argument).
    origin_hub_id: Optional[str] = Field(
        default=None,
        description="Phase 999.9 D-04: origin hub identifier",
    )


class RateResult(BaseModel):
    """Rate table lookup output.

    Args:
        base_rate: Base rate in THB.
        currency: Currency code (default "THB").
        rate_tier: Weight tier description (e.g., "0-5kg").
    """

    base_rate: float = Field(description="Base rate in THB")
    currency: str = Field(default="THB")
    rate_tier: str = Field(description="Weight tier description")


# ----- Phase 5 search models (TOOL-05) -----


class SearchInput(BaseModel):
    """Input for search_fuel_news tool (TOOL-05)."""

    query: str = Field(min_length=1, description="Normalized search query")
    max_results: int = Field(default=5, ge=1, le=10)


class SearchSource(BaseModel):
    """One ranked Tavily news result."""

    title: str
    url: str
    snippet: str = Field(default="", description="First ~240 chars of content")
    published_at: Optional[str] = Field(
        default=None,
        description="Tavily 'published_date' (ISO-8601 when present)",
    )


class SearchResult(BaseModel):
    """Output of search_fuel_news (D-11 search_context shape)."""

    query: str
    summary: Optional[str] = Field(
        default=None,
        description="1-line LLM-generated answer from Tavily 'answer' field",
    )
    sources: List[SearchSource] = Field(default_factory=list)
    fetched_at: str = Field(
        description="ISO-8601 UTC with 'Z' suffix (Phase 3 D-13 pattern)"
    )
