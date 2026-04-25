"""Wave 0 placeholder tests for pricing_agent_node (ORCH-04).

Real implementations land in Plan 03-02 (nodes). These stubs ensure the
test names are grep-discoverable and the file is collected by pytest from
day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-02"
)


def test_computes_surcharge_and_emits_trace():
    # Implemented in Plan 03-02
    ...


def test_bubbles_value_error_from_lookup_rate():
    # Implemented in Plan 03-02
    ...


def test_gemini_failure_deterministic_fallback():
    # Implemented in Plan 03-02
    ...
