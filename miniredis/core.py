from __future__ import annotations

import math
import time

from protocol import JSONValue


class MiniRedisStore:
    def __init__(self) -> None:
        self._data: dict[str, JSONValue] = {}
        self._expires: dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        if key in self._expires and time.monotonic() >= self._expires[key]:
            self._data.pop(key, None)
            del self._expires[key]
            return True
        return False

    def set(self, key: str, value: JSONValue, ttl_seconds: int | None = None) -> None:
        self._data[key] = value
        if ttl_seconds is not None:
            self._expires[key] = time.monotonic() + ttl_seconds
        elif key in self._expires:
            del self._expires[key]

    def get(self, key: str) -> JSONValue | None:
        if key not in self._data or self._is_expired(key):
            return None
        return self._data[key]

    def delete(self, key: str) -> bool:
        if key not in self._data or self._is_expired(key):
            return False
        del self._data[key]
        self._expires.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        if key not in self._data or self._is_expired(key):
            return False
        return True

    def expire(self, key: str, ttl_seconds: int) -> bool:
        if key not in self._data or self._is_expired(key):
            return False
        self._expires[key] = time.monotonic() + ttl_seconds
        return True

    def ttl(self, key: str) -> int | None:
        if key not in self._data or self._is_expired(key):
            return None
        if key not in self._expires:
            return None

        remaining = self._expires[key] - time.monotonic()
        if remaining <= 0:
            self._is_expired(key)
            return None
        return math.ceil(remaining)

    def cleanup_expired(self) -> int:
        removed = 0
        for key in list(self._expires.keys()):
            if self._is_expired(key):
                removed += 1
        return removed
