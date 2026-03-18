from __future__ import annotations

import time

from protocol import JSONValue


class MiniRedisStore:
    def __init__(self) -> None:
        """저장소와 TTL 상태를 초기화한다."""

        # dict[key타입힌트, value타입힌트]
        self._data: dict[str, JSONValue] = {}
        self._expires: dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        if key in self._expires and time.monotonic() >= self._expires[key]:
            del self._data[key]
            del self._expires[key]
            return True
        return False

    def set(self, key: str, value: JSONValue, ttl_seconds: int | None = None) -> None:
        """키에 JSON 값을 저장하고 필요하면 TTL을 설정한다."""
        self._data[key] = value
        if ttl_seconds is not None:
            self._expires[key] = time.monotonic() + ttl_seconds
        elif key in self._expires:
            del self._expires[key]

    def get(self, key: str) -> JSONValue | None:
        """키가 존재하고 만료되지 않았으면 값을 반환한다."""
        if key not in self._data or self._is_expired(key):
            return None
        return self._data[key]

    def delete(self, key: str) -> bool:
        """키를 삭제하고 실제로 삭제됐는지 반환한다."""
        if key not in self._data or self._is_expired(key):
            return False
        del self._data[key]
        self._expires.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        """키가 현재 유효하게 존재하는지 확인한다."""
        if key not in self._data or self._is_expired(key):
            return False
        return True

    # TODO: 시간 남으면 하기
    # def expire(self, key: str, ttl_seconds: int) -> bool:
    #     """기존 키에 TTL을 설정하거나 갱신한다."""
    #     pass
    #
    # def ttl(self, key: str) -> int | None:
    #     pass
    #
    # def cleanup_expired(self) -> int:
    #     pass
