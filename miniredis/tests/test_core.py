from core import MiniRedisStore


def test_키_설정_조회_삭제_존재확인() -> None:
    # Given: 저장소를 비어 있는 상태로 준비한다.
    store = MiniRedisStore()

    # When: 키-값을 저장하고 조회/삭제를 수행한다.
    store.set("name", "value")

    # Then: 조회/존재/삭제 동작이 기대대로 동작한다.
    assert store.get("name") == "value"
    assert store.exists("name") is True

    deleted = store.delete("name")
    assert deleted is True
    assert store.get("name") is None
    assert store.exists("name") is False


def test_만료시간_기능_보류() -> None:
    # Given: expire/ttl/cleanup_expired 기능은 다음 단계로 미룬 상태다.
    # Then: 보류 상태임을 남겨둔다.
    assert True
