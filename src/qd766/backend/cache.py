from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True)
class CacheStats:
    entries: int
    in_flight: int
    hits: int
    misses: int
    waits: int


@dataclass
class _Entry(Generic[V]):
    value: V
    expires_at: float


class SingleFlightTTLCache(Generic[K, V]):
    """Small process-local TTL cache with one loader per key at a time."""

    def __init__(self, ttl_seconds: float, *, clock: Callable[[], float] = time.monotonic,
                 max_entries: int | None = None):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries is not None and (type(max_entries) is not int or max_entries <= 0):
            raise ValueError("max_entries must be a positive integer")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._clock = clock
        self._condition = threading.Condition()
        self._entries: dict[K, _Entry[V]] = {}
        self._in_flight: set[K] = set()
        self._hits = 0
        self._misses = 0
        self._waits = 0

    def get_or_load(self, key: K, loader: Callable[[], V]) -> tuple[V, str]:
        waited = False
        with self._condition:
            while True:
                now = self._clock()
                if self.max_entries is not None:
                    # Opt-in bounded caches prune on reads; existing caches keep
                    # their original behavior when no capacity is configured.
                    for expired in [k for k, v in self._entries.items() if v.expires_at <= now]:
                        self._entries.pop(expired, None)
                entry = self._entries.get(key)
                if entry is not None and entry.expires_at > now:
                    self._hits += 1
                    return entry.value, "shared" if waited else "hit"
                if entry is not None:
                    self._entries.pop(key, None)
                if key not in self._in_flight:
                    self._in_flight.add(key)
                    self._misses += 1
                    break
                if not waited:
                    self._waits += 1
                    waited = True
                self._condition.wait()

        try:
            value = loader()
        except Exception:
            with self._condition:
                self._in_flight.discard(key)
                self._condition.notify_all()
            raise

        with self._condition:
            if self.max_entries is not None and key not in self._entries:
                while len(self._entries) >= self.max_entries:
                    oldest = min(self._entries, key=lambda k: self._entries[k].expires_at)
                    self._entries.pop(oldest, None)
            self._entries[key] = _Entry(value, self._clock() + self.ttl_seconds)
            self._in_flight.discard(key)
            self._condition.notify_all()
        return value, "miss"

    def clear(self) -> None:
        with self._condition:
            self._entries.clear()
            self._condition.notify_all()

    def stats(self) -> CacheStats:
        with self._condition:
            now = self._clock()
            expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
            for key in expired:
                self._entries.pop(key, None)
            return CacheStats(
                entries=len(self._entries),
                in_flight=len(self._in_flight),
                hits=self._hits,
                misses=self._misses,
                waits=self._waits,
            )
