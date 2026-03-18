from core import MiniRedisStore


def test_set_get_delete_exists() -> None:
    # Given: 빈 저장소 상태에서 기본 동작만 확인한다.
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


def test_ttl_timing_features_reserved() -> None:
    # Given: expire/ttl/cleanup 기능은 이번 단계에서 미룬다.
    # Then: 나중 구현을 위해 보류로 남겨 둔다.
    assert True
