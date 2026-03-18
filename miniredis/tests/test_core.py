import sys
from pathlib import Path
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core import MiniRedisStore


def test_키_설정_조회_삭제_존재_확인() -> None:
    # Given: 저장소에 기본 키-값이 비어 있는 상태를 준비한다.
    store = MiniRedisStore()

    # When: 키를 설정하고, 조회/삭제를 수행한다.
    store.set("name", "value")

    # Then: 조회값과 존재 여부, 삭제 결과가 기대대로 동작한다.
    assert store.get("name") == "value"
    assert store.exists("name") is True

    deleted = store.delete("name")
    assert deleted is True
    assert store.get("name") is None
    assert store.exists("name") is False


def test_키_만료_후_조회_실패() -> None:
    # Given: TTL 1초가 지정된 키를 저장한다.
    store = MiniRedisStore()

    # When: 1초 이상 경과 후 조회한다.
    store.set("temp", "x", ttl_seconds=1)
    assert store.exists("temp") is True

    time.sleep(1.1)

    # Then: 키가 만료되어 조회 및 존재 확인 모두 실패한다.
    assert store.get("temp") is None
    assert store.exists("temp") is False


# def test_만료시간_연장_및_ttl_확인() -> None:
#     # Given: 만료 시간을 아직 갖지 않은 키와 TTL이 없는 키를 준비한다.
#     store = MiniRedisStore()
#
#     # When: 키에 TTL을 부여하고, TTL을 조회한다.
#     store.set("session", "abc")
#     assert store.expire("session", 1) is True
#     ttl = store.ttl("session")
#
#     # Then: TTL 조회가 정수로 반환되고, 영속 키는 None이 반환된다.
#     assert isinstance(ttl, int)
#     assert ttl >= 0
#
#     store.set("persistent", "y")
#     assert store.ttl("persistent") is None


def test_만료키_일괄_정리() -> None:
    # Given: 만료 키 2개와 영구 키 1개를 준비한다.
    store = MiniRedisStore()

    # When: TTL 경과 후 만료 정리를 실행한다.
    store.set("a", 1, ttl_seconds=1)
    store.set("b", 2, ttl_seconds=1)
    store.set("c", 3)

    time.sleep(1.1)
    cleaned = store.cleanup_expired()

    # Then: 만료된 키 개수와 잔존 값이 기대대로이다.
    assert cleaned == 2
    assert store.exists("a") is False
    assert store.exists("b") is False
    assert store.get("c") == 3
