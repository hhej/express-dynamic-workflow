"""In-process TTL cache used by calculate_route (D-07).

Deliberately minimal — resets on process restart, which is acceptable for
dev and demo. Thread-safe via a Lock so parallel agent execution (Phase 5)
does not corrupt the store.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Generic, Optional, TypeVar

__all__ = ["TTLCache"]

V = TypeVar("V")


@dataclass
class TTLCache(Generic[V]):
    """Minimal in-process TTL cache.

    Args:
        ttl_seconds: Time-to-live for each entry. Expired entries are
            removed lazily on the next get() call.
    """

    ttl_seconds: int
    _store: dict = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def get(self, key) -> Optional[V]:
        """Return the cached value for ``key`` or None if missing/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, stored_at = entry
            if time.time() - stored_at > self.ttl_seconds:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key, value: V) -> None:
        """Store ``value`` under ``key`` with the current timestamp."""
        with self._lock:
            self._store[key] = (value, time.time())

    def clear(self) -> None:
        """Remove all entries (used by tests)."""
        with self._lock:
            self._store.clear()
