"""Wave 0 placeholder tests for GET /api/fuel-prices (API-03).

Real implementations land in Plan 03-05 (fuel-prices endpoint). These
stubs ensure the test names are grep-discoverable and the file is
collected by pytest from day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-05"
)


def test_returns_last_30_days():
    # Implemented in Plan 03-05
    ...


def test_clamps_to_available():
    # Implemented in Plan 03-05
    ...
