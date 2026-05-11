"""Phase 999.10 adversarial-pack regression — REFUSAL_COPY parity (RED stub).

This is the TDD RED-phase stub: an asserts-False placeholder that proves the
test wiring (collection, import path) is correct BEFORE the full
implementation lands in the GREEN commit.

Replaced wholesale in the next commit by the four-case parametrised regression
+ legit-baseline false-positive guard.
"""
from __future__ import annotations


def test_red_stub_must_fail_until_green_phase():
    """Intentionally failing test so the RED commit shows red.

    Replaced in the next commit by the real adversarial-pack regression
    suite (4 parametrised refusal cases + 1 legit-baseline guard).
    """
    assert False, "RED phase stub — replaced by real tests in GREEN commit"
