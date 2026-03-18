from __future__ import annotations

import threading
import time

from protocol import JSONValue


class MiniRedisStore:
    def __init__(self) -> None:
        self._store: dict[str, tuple[JSONValue, float | None]] = {}
        self._lock = threading.Lock()

    def _now(self) -> float:
        return time.time()

    def _cleanup_expired_locked(self, now: float) -> int:
        expired_keys: list[str] = [
            key for key, (_, expire_at) in self._store.items() if expire_at is not None and expire_at <= now
        ]
        for key in expired_keys:
            self._store.pop(key, None)
        return len(expired_keys)

    def _is_expired(self, key: str, now: float) -> bool:
        expire_at = self._store.get(key, (None, None))[1]
        return expire_at is not None and expire_at <= now

    def set(self, key: str, value: JSONValue, ttl_seconds: int | None = None) -> None:
        expire_at = self._now() + ttl_seconds if ttl_seconds is not None else None
        with self._lock:
            self._store[key] = (value, expire_at)

    def get(self, key: str) -> JSONValue | None:
        now = self._now()
        with self._lock:
            self._cleanup_expired_locked(now)
            entry = self._store.get(key)
            if entry is None:
                return None
            return entry[0]

    def delete(self, key: str) -> bool:
        with self._lock:
            self._cleanup_expired_locked(self._now())
            return self._store.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        now = self._now()
        with self._lock:
            if self._is_expired(key, now):
                self._store.pop(key, None)
                return False
            return key in self._store

    def expire(self, key: str, ttl_seconds: int) -> bool:
        now = self._now()
        with self._lock:
            if key not in self._store or self._is_expired(key, now):
                self._store.pop(key, None)
                return False
            self._store[key] = (self._store[key][0], now + ttl_seconds)
            return True

    def ttl(self, key: str) -> int | None:
        now = self._now()
        with self._lock:
            if key not in self._store or self._is_expired(key, now):
                self._store.pop(key, None)
                return None
            _, expire_at = self._store[key]
            if expire_at is None:
                return None
            return max(0, int(expire_at - now))

    def cleanup_expired(self) -> int:
        with self._lock:
            return self._cleanup_expired_locked(self._now())
