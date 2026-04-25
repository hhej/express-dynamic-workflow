"""Wave 0 placeholder tests for /api/conversations endpoints (API-02).

Real implementations land in Plan 03-05 (conversation + fuel-prices
endpoints). These stubs ensure the test names are grep-discoverable and
the file is collected by pytest from day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-05"
)


def test_lists_conversations_desc():
    # Implemented in Plan 03-05
    ...


def test_returns_thread_state():
    # Implemented in Plan 03-05
    ...


def test_404_unknown_thread():
    # Implemented in Plan 03-05
    ...
