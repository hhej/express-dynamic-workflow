"""Wave 0 placeholder tests for planner_node (ORCH-01).

Real implementations land in Plan 03-02 (nodes). These stubs ensure the
test names are grep-discoverable and the file is collected by pytest from
day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-02"
)


def test_routes_to_fetch_fuel_on_fresh_query():
    # Implemented in Plan 03-02
    ...


def test_skips_fetch_when_fuel_fresh():
    # Implemented in Plan 03-02
    ...


def test_emits_clarify_on_missing_fields():
    # Implemented in Plan 03-02
    ...


def test_loop_budget_exhaustion_forces_respond():
    # Implemented in Plan 03-02
    ...


def test_parse_failure_falls_back_to_clarify():
    # Implemented in Plan 03-02
    ...
