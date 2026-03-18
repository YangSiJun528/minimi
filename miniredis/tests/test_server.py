import sys
from pathlib import Path
import asyncio

sys.path.append(str(Path(__file__).resolve().parents[1]))

from protocol import KeyRequest, SetRequest
from server import delete_value, exists_value, get_value, healthcheck, set_value


def run(coro):
    return asyncio.run(coro)


import pytest


@pytest.fixture(autouse=True)
def clear_store():
    # Given: 서버 상태 초기화는 core 담당이라 본 테스트에서는 스텁으로 처리한다.
    yield
    # Then: 테스트 간 교차 영향 제거도 core가 구현될 때 확정한다.


def test_헬스체크_성공() -> None:
    # Given: 서버가 실행 가능한 상태로 준비되어 있다.
    # When: 헬스체크 엔드포인트를 호출한다.
    response = run(healthcheck())

    # Then: 성공 응답을 받는다.
    assert response.success is True
    assert response.message == "ok"


def test_set_조회_삭제_흐름() -> None:
    # Given: 임시 키가 없는 빈 상태에서 시작한다.
    created = run(set_value(SetRequest(key="k", value={"a": 1})))

    # When: 저장 후 조회하고, 존재 조회 후 삭제를 수행한다.
    assert created.success is True

    got = run(get_value(KeyRequest(key="k")))
    exists = run(exists_value(KeyRequest(key="k")))
    deleted = run(delete_value(KeyRequest(key="k")))
    not_exists = run(exists_value(KeyRequest(key="k")))

    # Then: 조회/존재/삭제 결과가 정상적으로 이어진다.
    assert got.success is True
    assert got.found is True
    assert got.key == "k"
    assert got.value == {"a": 1}

    assert exists.success is True
    assert exists.exists is True

    assert deleted.success is True
    assert deleted.message == "deleted"

    assert not_exists.success is False
    assert not_exists.exists is False


# def test_ttl_만료_및_정리() -> None:
#     # Given: TTL 1초로 키를 저장한다.
#     created = run(set_value(SetRequest(key="t", value="x", ttl_seconds=1)))
#
#     # When: TTL 조회 후 1초 이상 경과시 조회 및 정리를 수행한다.
#     assert created.success is True
#
#     ttl = run(ttl_value(KeyRequest(key="t")))
#     assert ttl.success is True
#     assert ttl.found is True
#     assert isinstance(ttl.ttl_seconds, int)
#     assert ttl.ttl_seconds >= 0
#
#     from time import sleep
#
#     sleep(1.1)
#     after = run(get_value(KeyRequest(key="t")))
#     cleaned = run(cleanup_expired())
#
#     # Then: 조회가 실패하고 cleanup 결과 메시지가 반환된다.
#     assert after.found is False
#     assert cleaned.success is True
#     assert "cleaned=" in cleaned.message


# def test_만료시간_연장_확인() -> None:
#     # Given: 영구 키를 먼저 저장한다.
#     run(set_value(SetRequest(key="e", value="z")))
#
#     # When: 만료 시간을 새로 설정하고 TTL을 조회한다.
#     ok = run(expire_value(ExpireRequest(key="e", ttl_seconds=2)))
#
#     # Then: 만료 갱신이 성공하고 TTL이 1 이상 반환된다.
#     assert ok.success is True
#     ttl = run(ttl_value(KeyRequest(key="e")))
#     assert ttl.ttl_seconds is not None
#     assert ttl.ttl_seconds >= 1
