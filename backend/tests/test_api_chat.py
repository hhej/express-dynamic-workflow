"""Wave 0 placeholder tests for POST /api/chat (API-01).

Real implementations land in Plan 03-04 (chat endpoint). These stubs
ensure the test names are grep-discoverable and the file is collected by
pytest from day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-04"
)


def test_happy_path_sse_sequence():
    # Implemented in Plan 03-04
    ...


def test_error_sse_sequence():
    # Implemented in Plan 03-04
    ...


def test_server_generates_thread_id():
    # Implemented in Plan 03-04
    ...
