from __future__ import annotations

from math import ceil
from threading import RLock
from time import time as default_time

from protocol import JSONValue


class MiniRedisStore:
    def __init__(self, clock=default_time) -> None:
        """저장소와 TTL 상태를 초기화한다."""
        self._clock = clock
        self._store: dict[str, JSONValue] = {}
        self._expires_at: dict[str, float] = {}
        self._lock = RLock()

    def set(self, key: str, value: JSONValue, ttl_seconds: int | None = None) -> None:
        """키에 JSON 값을 저장하고 필요하면 TTL을 설정한다."""
        with self._lock:
            self._store[key] = value
            if ttl_seconds is None:
                self._expires_at.pop(key, None)
            else:
                self._expires_at[key] = self._clock() + ttl_seconds

    def get(self, key: str) -> JSONValue | None:
        """키가 존재하고 만료되지 않았으면 값을 반환한다."""
        with self._lock:
            self._purge_if_expired(key)
            return self._store.get(key)

    def delete(self, key: str) -> bool:
        """키를 삭제하고 실제로 삭제됐는지 반환한다."""
        with self._lock:
            self._purge_if_expired(key)
            existed = key in self._store
            self._store.pop(key, None)
            self._expires_at.pop(key, None)
            return existed

    def exists(self, key: str) -> bool:
        """키가 현재 유효하게 존재하는지 확인한다."""
        with self._lock:
            self._purge_if_expired(key)
            return key in self._store

    def expire(self, key: str, ttl_seconds: int) -> bool:
        """기존 키에 TTL을 설정하거나 갱신한다."""
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._store:
                return False
            self._expires_at[key] = self._clock() + ttl_seconds
            return True

    def ttl(self, key: str) -> int | None:
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._store:
                return None
            expires_at = self._expires_at.get(key)
            if expires_at is None:
                return None
            remaining = expires_at - self._clock()
            if remaining <= 0:
                self._delete_unlocked(key)
                return None
            return ceil(remaining)

    def cleanup_expired(self) -> int:
        with self._lock:
            expired_keys = [
                key for key, expires_at in self._expires_at.items() if expires_at <= self._clock()
            ]
            for key in expired_keys:
                self._delete_unlocked(key)
            return len(expired_keys)

    def _purge_if_expired(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at is not None and expires_at <= self._clock():
            self._delete_unlocked(key)

    def _delete_unlocked(self, key: str) -> None:
        self._store.pop(key, None)
        self._expires_at.pop(key, None)
