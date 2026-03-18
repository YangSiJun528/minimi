from __future__ import annotations

from protocol import JSONValue


class MiniRedisStore:
    def __init__(self) -> None:
        """저장소와 TTL 상태를 초기화한다."""
        pass

    def set(self, key: str, value: JSONValue, ttl_seconds: int | None = None) -> None:
        """키에 JSON 값을 저장하고 필요하면 TTL을 설정한다."""
        pass

    def get(self, key: str) -> JSONValue | None:
        """키가 존재하고 만료되지 않았으면 값을 반환한다."""
        pass

    def delete(self, key: str) -> bool:
        """키를 삭제하고 실제로 삭제됐는지 반환한다."""
        pass

    def exists(self, key: str) -> bool:
        """키가 현재 유효하게 존재하는지 확인한다."""
        pass

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
