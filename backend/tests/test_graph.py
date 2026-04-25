"""Wave 0 placeholder tests for graph assembly (ORCH-06, ORCH-08, ORCH-10).

Real implementations land in Plan 03-03 (graph). These stubs ensure the
test names are grep-discoverable and the file is collected by pytest from
day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-03"
)


def test_retry_policy_retries_httpx_error():
    # Implemented in Plan 03-03
    ...


def test_retry_exhaustion_routes_to_response_partial():
    # Implemented in Plan 03-03
    ...


def test_value_error_skips_retry():
    # Implemented in Plan 03-03
    ...


def test_checkpointer_persists_across_invocations():
    # Implemented in Plan 03-03
    ...


def test_followup_reuses_cached_fuel():
    # Implemented in Plan 03-03
    ...


def test_full_surcharge_query_integration():
    # Implemented in Plan 03-03
    ...


def test_followup_only_runs_pricing():
    # Implemented in Plan 03-03
    ...
