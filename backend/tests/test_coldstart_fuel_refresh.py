"""Tests for the cold-start fuel-CSV refresh contract (Quick 260509-eum).

Covers:
  - ``is_csv_stale(csv_path, today)`` predicate (D-01 timezone-aware)
  - ``refresh_csv(today)`` reusable wrapper (D-03 log-and-continue)
  - FastAPI lifespan integration (D-02 background asyncio.create_task,
    EXPRESS_SKIP_COLDSTART_REFRESH opt-out)

NEVER hits the live network -- ``_scrape_eppo`` is monkeypatched and
the lifespan tests opt out via the env flag or a recording stub.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import logging
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "data" / "scripts"


def _load_fetch_module():
    """Load data/scripts/fetch_fuel_prices.py as a fresh module.

    Mirrors the helper in test_fuel_prices.py so we exercise the live
    script file (not a cached import).
    """
    spec = importlib.util.spec_from_file_location(
        "_fetch_fuel_prices_under_test_coldstart",
        SCRIPTS_DIR / "fetch_fuel_prices.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# is_csv_stale() -- D-01 timezone-aware staleness predicate
# ---------------------------------------------------------------------------


class TestIsCsvStale:
    """Predicate: True iff max(date) in CSV is strictly < today (Asia/Bangkok)."""

    @staticmethod
    def _write_csv(path: Path, dates: list[str]) -> None:
        df = pd.DataFrame(
            {
                "date": dates,
                "diesel_b7_price": [30.0] * len(dates),
                "source": ["eppo"] * len(dates),
            }
        )
        df.to_csv(path, index=False)

    def test_is_csv_stale_returns_true_when_max_date_before_today(self, tmp_path):
        """CSV's latest row is older than today -> stale."""
        module = _load_fetch_module()
        csv = tmp_path / "stale.csv"
        self._write_csv(csv, ["2026-04-01", "2026-04-03"])

        assert module.is_csv_stale(csv, today=date(2026, 5, 9)) is True

    def test_is_csv_stale_returns_false_when_max_date_equals_today(self, tmp_path):
        """Boundary: max(date) == today is NOT stale (D-01 strict <)."""
        module = _load_fetch_module()
        csv = tmp_path / "fresh.csv"
        self._write_csv(csv, ["2026-05-08", "2026-05-09"])

        assert module.is_csv_stale(csv, today=date(2026, 5, 9)) is False

    def test_is_csv_stale_returns_false_when_max_date_after_today(self, tmp_path):
        """Clock-skew safe: max(date) > today is NOT stale."""
        module = _load_fetch_module()
        csv = tmp_path / "future.csv"
        self._write_csv(csv, ["2026-05-09", "2026-05-10"])

        assert module.is_csv_stale(csv, today=date(2026, 5, 9)) is False

    def test_is_csv_stale_returns_true_when_csv_missing(self, tmp_path):
        """Missing file forces a refresh attempt."""
        module = _load_fetch_module()
        csv = tmp_path / "does_not_exist.csv"
        assert not csv.exists()

        assert module.is_csv_stale(csv, today=date(2026, 5, 9)) is True

    def test_is_csv_stale_returns_true_when_csv_empty_or_unparseable(self, tmp_path):
        """File exists but has no parseable date rows -> stale."""
        module = _load_fetch_module()
        csv = tmp_path / "empty.csv"
        # Header only (no rows).
        csv.write_text("date,diesel_b7_price,source\n", encoding="utf-8")

        assert module.is_csv_stale(csv, today=date(2026, 5, 9)) is True

        # Garbage text -> pandas raises -> still stale.
        garbage = tmp_path / "garbage.csv"
        garbage.write_bytes(b"\x00\x01\x02 not a csv at all")
        assert module.is_csv_stale(garbage, today=date(2026, 5, 9)) is True

    def test_is_csv_stale_uses_bangkok_today_when_none_passed(
        self, tmp_path, monkeypatch
    ):
        """When today=None, the module's _today_bangkok() seam is used.

        Proves the predicate is NOT calling naive ``date.today()`` -- a
        host running in UTC must still resolve the Bangkok calendar day.
        """
        module = _load_fetch_module()
        csv = tmp_path / "fresh.csv"
        self._write_csv(csv, ["2026-05-09"])

        calls = []

        def fake_today():
            calls.append("called")
            return date(2026, 5, 9)

        monkeypatch.setattr(module, "_today_bangkok", fake_today)

        # CSV max == fake "today" -> NOT stale; AND _today_bangkok was hit.
        assert module.is_csv_stale(csv, today=None) is False
        assert calls == ["called"]


# ---------------------------------------------------------------------------
# refresh_csv() -- D-03 log-and-continue wrapper around _scrape_eppo
# ---------------------------------------------------------------------------


class TestRefreshCsv:
    """Wrapper contract: skip when fresh, scrape+write when stale, swallow on error."""

    def test_refresh_csv_returns_false_and_skips_scrape_when_fresh(
        self, tmp_path, monkeypatch
    ):
        """Fresh CSV: refresh_csv must NOT call _scrape_eppo and returns False."""
        module = _load_fetch_module()
        csv = tmp_path / "fresh.csv"
        TestIsCsvStale._write_csv(csv, ["2026-05-09"])
        # Point the module's OUTPUT_PATH at our temp CSV so refresh_csv
        # checks freshness against it.
        monkeypatch.setattr(module, "OUTPUT_PATH", csv)

        scrape_calls = []

        def boom():
            scrape_calls.append("called")
            raise RuntimeError("scrape must NOT be invoked when CSV is fresh")

        monkeypatch.setattr(module, "_scrape_eppo", boom)

        result = module.refresh_csv(today=date(2026, 5, 9))

        assert result is False
        assert scrape_calls == []

    def test_refresh_csv_returns_true_and_writes_when_stale_and_scrape_succeeds(
        self, tmp_path, monkeypatch
    ):
        """Stale + scrape OK: writes to OUTPUT_PATH and returns True."""
        module = _load_fetch_module()
        csv = tmp_path / "out.csv"
        # Pre-populate with a stale row so the predicate fires.
        TestIsCsvStale._write_csv(csv, ["2026-04-01"])
        monkeypatch.setattr(module, "OUTPUT_PATH", csv)

        synthetic = pd.DataFrame(
            {
                "date": ["2026-05-08", "2026-05-09"],
                "diesel_b7_price": [31.10, 31.20],
                "source": ["eppo", "eppo"],
            }
        )
        monkeypatch.setattr(module, "_scrape_eppo", lambda: synthetic)

        result = module.refresh_csv(today=date(2026, 5, 9))

        assert result is True
        written = pd.read_csv(csv)
        assert len(written) == 2
        assert set(written.columns) == {"date", "diesel_b7_price", "source"}
        assert written["date"].tolist() == ["2026-05-08", "2026-05-09"]

    def test_refresh_csv_returns_false_when_scrape_raises(
        self, tmp_path, monkeypatch, caplog
    ):
        """Stale + scrape fails: existing CSV untouched, returns False, logs WARNING."""
        module = _load_fetch_module()
        csv = tmp_path / "out.csv"
        TestIsCsvStale._write_csv(csv, ["2026-04-01"])
        monkeypatch.setattr(module, "OUTPUT_PATH", csv)

        before_bytes = csv.read_bytes()

        def boom():
            raise RuntimeError("simulated EPPO outage")

        monkeypatch.setattr(module, "_scrape_eppo", boom)

        with caplog.at_level(logging.WARNING, logger=module.logger.name):
            result = module.refresh_csv(today=date(2026, 5, 9))

        assert result is False
        # CSV must be byte-for-byte unchanged.
        assert csv.read_bytes() == before_bytes
        # WARNING line emitted (D-03 log-and-continue).
        assert any(
            "Cold-start fuel refresh failed" in rec.message
            for rec in caplog.records
            if rec.levelno >= logging.WARNING
        )


# ---------------------------------------------------------------------------
# Lifespan integration (Task 2) -- non-blocking background scheduling
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_stub_refresh(monkeypatch, tmp_path):
    """Reload backend.config + backend.api.main after stubbing the refresh.

    Yields ``(app, calls)`` where ``calls`` is a list the stub appends to
    on every invocation. Tests can install their own stub by re-patching
    ``backend.api.main.refresh_fuel_csv`` AFTER reload.
    """
    # Isolate checkpoint DB so concurrent tests don't collide.
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "checkpoints.db"))

    import backend.config as _cfg
    importlib.reload(_cfg)
    import backend.api.main as _main
    importlib.reload(_main)

    calls: list[tuple] = []

    def stub(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr(_main, "refresh_fuel_csv", stub)
    return _main, calls


def test_lifespan_schedules_refresh_as_background_task_by_default(
    app_with_stub_refresh, monkeypatch
):
    """Default behaviour: lifespan schedules refresh via asyncio.create_task.

    /health responds 200 (proves no await-block) and the recording stub
    is invoked exactly once within a short bounded wait.
    """
    monkeypatch.delenv("EXPRESS_SKIP_COLDSTART_REFRESH", raising=False)
    main_mod, calls = app_with_stub_refresh

    with TestClient(main_mod.app) as client:
        # /health must succeed BEFORE we wait for the background task --
        # that's the non-blocking gate (D-02).
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["graph_ready"] is True

        # The background task lives on app.state. Wait for it bounded.
        task = getattr(main_mod.app.state, "coldstart_refresh_task", None)
        assert task is not None, "lifespan must store task on app.state"

        async def _wait():
            await asyncio.wait_for(task, timeout=2.0)

        asyncio.run(_wait())

    assert len(calls) == 1, f"refresh stub called {len(calls)} times, want 1"


def test_lifespan_skips_refresh_when_env_flag_set(
    monkeypatch, tmp_path
):
    """EXPRESS_SKIP_COLDSTART_REFRESH=1 disables the cold-start path entirely.

    Set the env var BEFORE reloading config so the module-level flag picks
    it up. Stub MUST NOT be called and /health still 200s.
    """
    monkeypatch.setenv("EXPRESS_SKIP_COLDSTART_REFRESH", "1")
    monkeypatch.setenv("CHECKPOINT_PATH", str(tmp_path / "checkpoints.db"))

    import backend.config as _cfg
    importlib.reload(_cfg)
    assert _cfg.EXPRESS_SKIP_COLDSTART_REFRESH is True
    import backend.api.main as _main
    importlib.reload(_main)

    calls: list[tuple] = []

    def stub(*args, **kwargs):
        calls.append((args, kwargs))
        return True

    monkeypatch.setattr(_main, "refresh_fuel_csv", stub)

    with TestClient(_main.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        # No task scheduled when flag is set.
        assert getattr(_main.app.state, "coldstart_refresh_task", None) is None

    assert calls == []


def test_lifespan_swallows_refresh_exception(
    app_with_stub_refresh, monkeypatch, caplog
):
    """If the refresh raises, lifespan still enters/exits cleanly + WARNING logged.

    D-03: log-and-continue. /health must still return 200 and the
    background task's exception must be captured (not propagated).
    """
    monkeypatch.delenv("EXPRESS_SKIP_COLDSTART_REFRESH", raising=False)
    main_mod, _calls = app_with_stub_refresh

    def explode(*args, **kwargs):
        raise RuntimeError("simulated scrape blowup")

    monkeypatch.setattr(main_mod, "refresh_fuel_csv", explode)

    with caplog.at_level(logging.WARNING, logger=main_mod.logger.name):
        with TestClient(main_mod.app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

            task = getattr(main_mod.app.state, "coldstart_refresh_task", None)
            assert task is not None

            # Drain the task; outer net in _coldstart_fuel_refresh swallows.
            async def _wait():
                await asyncio.wait_for(task, timeout=2.0)

            asyncio.run(_wait())

    # WARNING line emitted by either refresh_csv (inner) or
    # _coldstart_fuel_refresh (outer net). The stub bypasses refresh_csv
    # entirely, so the warning MUST come from the outer net.
    assert any(
        "Cold-start fuel CSV refresh" in rec.message
        and rec.levelno >= logging.WARNING
        for rec in caplog.records
    ), f"expected WARNING log; got: {[r.message for r in caplog.records]}"
