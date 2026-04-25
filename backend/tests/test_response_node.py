"""Wave 0 placeholder tests for response_node (ORCH-05).

Real implementations land in Plan 03-02 (nodes). These stubs ensure the
test names are grep-discoverable and the file is collected by pytest from
day one.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Wave 0 placeholder; implementation lands in Plan 03-02"
)


def test_renders_locked_markdown_structure():
    # Implemented in Plan 03-02
    ...


def test_partial_status_on_errors():
    # Implemented in Plan 03-02
    ...


def test_clarify_status():
    # Implemented in Plan 03-02
    ...


def test_cap_callout_prepended():
    # Implemented in Plan 03-02
    ...
