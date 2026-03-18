from __future__ import annotations

import sys
import time
from unittest.mock import patch

import pytest

from core import MiniRedisStore

#TODO:
#   이거 개별적으로 다 실행되는건지? 서로 영향 없는건지 검증
#   테스트코드가 너무 내부 구현에 의존하면서 동작하지 않나?

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> MiniRedisStore:
    return MiniRedisStore()


# ===========================================================================
# SET / GET 기본 동작
# ===========================================================================

class TestSetGet:
    def test_문자열을_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "hello")

        # When
        result = store.get("k")

        # Then
        assert result == "hello"

    def test_정수를_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", 42)

        # When
        result = store.get("k")

        # Then
        assert result == 42

    def test_실수를_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", 3.14)

        # When
        result = store.get("k")

        # Then
        assert result == 3.14

    def test_불리언을_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", True)

        # When
        result = store.get("k")

        # Then
        assert result is True

    def test_None값을_저장하면_키없음과_구분할_수_없다(self, store: MiniRedisStore) -> None:
        # Given — 값이 None인 키를 저장
        store.set("k", None)

        # When
        result = store.get("k")

        # Then — get()이 '키 없음'과 '값이 None'을 구분하지 못하는 한계
        assert result is None

    def test_리스트를_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", [1, "two", None, True])

        # When
        result = store.get("k")

        # Then
        assert result == [1, "two", None, True]

    def test_딕셔너리를_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", {"nested": {"a": 1}})

        # When
        result = store.get("k")

        # Then
        assert result == {"nested": {"a": 1}}

    def test_깊게_중첩된_구조를_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        deep = {"a": [{"b": [{"c": 42}]}]}
        store.set("k", deep)

        # When
        result = store.get("k")

        # Then
        assert result == deep

    def test_존재하지_않는_키를_조회하면_None을_반환한다(self, store: MiniRedisStore) -> None:
        # Given — 빈 저장소

        # When
        result = store.get("no_such_key")

        # Then
        assert result is None

    def test_같은_키에_값을_덮어쓰면_최신_값이_반환된다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "old")

        # When
        store.set("k", "new")

        # Then
        assert store.get("k") == "new"

    def test_같은_키에_다른_타입으로_덮어쓸_수_있다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "string")

        # When
        store.set("k", 123)

        # Then
        assert store.get("k") == 123


# ===========================================================================
# 특수 키 이름
# ===========================================================================

class TestSpecialKeys:
    def test_빈_문자열을_키로_사용할_수_있다(self, store: MiniRedisStore) -> None:
        # Given & When
        store.set("", "value")

        # Then
        assert store.get("") == "value"

    def test_공백이_포함된_키를_사용할_수_있다(self, store: MiniRedisStore) -> None:
        # Given & When
        store.set("key with spaces", "v")

        # Then
        assert store.get("key with spaces") == "v"

    def test_유니코드_키를_사용할_수_있다(self, store: MiniRedisStore) -> None:
        # Given & When
        store.set("한글키", "값")

        # Then
        assert store.get("한글키") == "값"

    def test_매우_긴_키를_사용할_수_있다(self, store: MiniRedisStore) -> None:
        # Given
        long_key = "k" * 10_000

        # When
        store.set(long_key, "v")

        # Then
        assert store.get(long_key) == "v"

    def test_개행문자가_포함된_키를_사용할_수_있다(self, store: MiniRedisStore) -> None:
        # Given & When
        store.set("key\nwith\nnewlines", "v")

        # Then
        assert store.get("key\nwith\nnewlines") == "v"


# ===========================================================================
# TTL / 만료
# ===========================================================================

class TestTTL:
    def test_TTL_만료_전에는_값이_유지된다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v", ttl_seconds=100)

        # When
        result = store.get("k")

        # Then
        assert result == "v"

    def test_TTL_만료_직전에는_살아있고_만료_시점에는_사라진다(self, store: MiniRedisStore) -> None:
        # Given
        base = time.monotonic()
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=5)

            # When — 만료 직전
            mock_time.monotonic.return_value = base + 4.999

            # Then — 아직 살아있음
            assert store.get("k") == "v"

            # When — 정확히 만료 시점 (>= 조건)
            mock_time.monotonic.return_value = base + 5.0

            # Then — 만료됨
            assert store.get("k") is None

    def test_TTL_경계값에서_정확히_만료되고_내부_데이터도_정리된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=10)

            # When — monotonic() == expire_at
            mock_time.monotonic.return_value = base + 10.0

            # Then
            assert store.get("k") is None
            assert store.exists("k") is False

    def test_TTL이_있던_키를_TTL_없이_덮어쓰면_TTL이_제거된다(self, store: MiniRedisStore) -> None:
        # Given
        base = time.monotonic()
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=1)

            # When — TTL 없이 다시 set
            store.set("k", "v2")

            # Then — 시간이 아무리 지나도 만료되지 않음
            mock_time.monotonic.return_value = base + 1000
            assert store.get("k") == "v2"

    def test_TTL이_있던_키를_새_TTL로_덮어쓰면_TTL이_갱신된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=5)

            # When — 3초 후 새 TTL(10초)로 갱신
            mock_time.monotonic.return_value = base + 3
            store.set("k", "v2", ttl_seconds=10)

            # Then — 원래 TTL이었으면 만료됐을 시점(base+5)에 아직 살아있음
            mock_time.monotonic.return_value = base + 5
            assert store.get("k") == "v2"

            # Then — 새 TTL 만료 시점(base+3+10=base+13)에 만료됨
            mock_time.monotonic.return_value = base + 13
            assert store.get("k") is None

    def test_TTL_0초로_설정하면_즉시_만료된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base

            # When — ttl=0 → expire = base + 0 = base, 조회 시 monotonic() >= expire
            store.set("k", "v", ttl_seconds=0)

            # Then
            assert store.get("k") is None

    def test_만료_시_내부_data와_expires_모두에서_키가_제거된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=1)

            # When — 만료 트리거
            mock_time.monotonic.return_value = base + 1
            store.get("k")

            # Then
            assert "k" not in store._data
            assert "k" not in store._expires

    def test_expire로_기존_키의_TTL을_설정할_수_있다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v")

            # When
            result = store.expire("k", 5)

            # Then
            assert result is True
            assert store._expires["k"] == base + 5

    def test_ttl은_남은_초를_올림해서_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=5)

            # When
            mock_time.monotonic.return_value = base + 4.2

            # Then
            assert store.ttl("k") == 1

    def test_cleanup_expired는_만료된_키만_정리한다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("expired", "v", ttl_seconds=1)
            store.set("alive", "v", ttl_seconds=10)

            # When
            mock_time.monotonic.return_value = base + 2
            removed_count = store.cleanup_expired()

            # Then
            assert removed_count == 1
            assert store.exists("expired") is False
            assert store.exists("alive") is True


# ===========================================================================
# DELETE
# ===========================================================================

class TestDelete:
    def test_존재하는_키를_삭제하면_True를_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v")

        # When
        result = store.delete("k")

        # Then
        assert result is True
        assert store.get("k") is None

    def test_존재하지_않는_키를_삭제하면_False를_반환한다(self, store: MiniRedisStore) -> None:
        # Given — 빈 저장소

        # When
        result = store.delete("no_such_key")

        # Then
        assert result is False

    def test_삭제_시_TTL_메타데이터도_함께_제거된다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v", ttl_seconds=100)

        # When
        store.delete("k")

        # Then
        assert "k" not in store._expires

    def test_이미_만료된_키를_삭제하면_False를_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=1)

            # When — 만료 후 삭제 시도
            mock_time.monotonic.return_value = base + 2
            result = store.delete("k")

            # Then
            assert result is False

    def test_삭제_후_같은_키로_다시_저장할_수_있다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v1")
        store.delete("k")

        # When
        store.set("k", "v2")

        # Then
        assert store.get("k") == "v2"

    def test_같은_키를_두_번_삭제하면_두_번째는_False를_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v")

        # When
        first = store.delete("k")
        second = store.delete("k")

        # Then
        assert first is True
        assert second is False


# ===========================================================================
# EXISTS
# ===========================================================================

class TestExists:
    def test_존재하는_키는_True를_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v")

        # When & Then
        assert store.exists("k") is True

    def test_존재하지_않는_키는_False를_반환한다(self, store: MiniRedisStore) -> None:
        # Given — 빈 저장소

        # When & Then
        assert store.exists("no_such") is False

    def test_만료된_키는_False를_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=1)

            # When — 만료 후
            mock_time.monotonic.return_value = base + 1

            # Then
            assert store.exists("k") is False

    def test_삭제된_키는_False를_반환한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v")
        store.delete("k")

        # When & Then
        assert store.exists("k") is False


# ===========================================================================
# 여러 키 조합
# ===========================================================================

class TestMultipleKeys:
    def test_여러_키를_독립적으로_저장하고_조회한다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("a", 1)
        store.set("b", 2)
        store.set("c", 3)

        # When & Then
        assert store.get("a") == 1
        assert store.get("b") == 2
        assert store.get("c") == 3

    def test_하나를_삭제해도_다른_키에_영향이_없다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("a", 1)
        store.set("b", 2)

        # When
        store.delete("a")

        # Then
        assert store.get("b") == 2

    def test_TTL_있는_키와_없는_키가_공존할_때_서로_영향이_없다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("ephemeral", "gone", ttl_seconds=5)
            store.set("permanent", "stays")

            # When — TTL 키 만료 시점 이후
            mock_time.monotonic.return_value = base + 10

            # Then
            assert store.get("ephemeral") is None
            assert store.get("permanent") == "stays"


# ===========================================================================
# _is_expired 내부 메서드 직접 테스트
# ===========================================================================

class TestIsExpired:
    def test_TTL이_없는_키는_만료되지_않는다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v")

        # When & Then
        assert store._is_expired("k") is False

    def test_TTL_범위_안의_키는_만료되지_않는다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "v", ttl_seconds=100)

        # When & Then
        assert store._is_expired("k") is False

    def test_만료_시_data와_expires에서_키를_정리한다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("k", "v", ttl_seconds=1)

            # When
            mock_time.monotonic.return_value = base + 1
            result = store._is_expired("k")

            # Then
            assert result is True
            assert "k" not in store._data
            assert "k" not in store._expires

    def test_저장된_적_없는_키는_만료되지_않은_것으로_취급한다(self, store: MiniRedisStore) -> None:
        # Given — 빈 저장소

        # When & Then
        assert store._is_expired("nonexistent") is False


# ===========================================================================
# 값의 뮤터빌리티(mutability) — 저장 후 외부에서 변경 시 영향
# ===========================================================================

class TestMutability:
    def test_리스트를_저장하면_레퍼런스를_공유하므로_외부_변경이_반영된다(self, store: MiniRedisStore) -> None:
        # Given
        data = [1, 2, 3]
        store.set("k", data)

        # When — 원본 리스트를 외부에서 변경
        data.append(4)

        # Then — 얕은 복사를 하지 않으므로 내부 값도 변경됨
        assert store.get("k") == [1, 2, 3, 4]

    def test_딕셔너리를_저장하면_레퍼런스를_공유하므로_외부_변경이_반영된다(self, store: MiniRedisStore) -> None:
        # Given
        data = {"a": 1}
        store.set("k", data)

        # When — 원본 딕셔너리를 외부에서 변경
        data["b"] = 2

        # Then
        assert store.get("k") == {"a": 1, "b": 2}


# ===========================================================================
# 메모리 사용량 테스트
# ===========================================================================

class TestMemoryUsage:
    def test_삭제하면_data에서_키가_제거되어_메모리가_반환된다(self, store: MiniRedisStore) -> None:
        # Given
        large_value = "x" * 1_000_000
        store.set("big", large_value)
        assert sys.getsizeof(store._data["big"]) > 999_000

        # When
        store.delete("big")

        # Then
        assert "big" not in store._data

    def test_만료된_키를_접근하면_내부_데이터가_정리된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            store.set("big", "x" * 1_000_000, ttl_seconds=1)
            assert len(store._data) == 1

            # When — 만료 후 접근
            mock_time.monotonic.return_value = base + 1
            store.get("big")

            # Then
            assert len(store._data) == 0

    def test_같은_키에_덮어쓰면_이전_값_참조가_교체된다(self, store: MiniRedisStore) -> None:
        # Given
        store.set("k", "x" * 1_000_000)

        # When
        store.set("k", "tiny")

        # Then
        assert store.get("k") == "tiny"
        assert len(store._data) == 1

    def test_만_개의_키를_생성하고_삭제하면_data가_비워진다(self, store: MiniRedisStore) -> None:
        # Given
        for i in range(10_000):
            store.set(f"key_{i}", i)
        assert len(store._data) == 10_000

        # When
        for i in range(10_000):
            store.delete(f"key_{i}")

        # Then
        assert len(store._data) == 0

    def test_TTL_키가_만료되면_expires_메타데이터도_정리된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            for i in range(100):
                store.set(f"k{i}", "v", ttl_seconds=1)

            # When — 만료 후 전부 접근하여 트리거
            mock_time.monotonic.return_value = base + 2
            for i in range(100):
                store.get(f"k{i}")

            # Then
            assert len(store._expires) == 0
            assert len(store._data) == 0

    def test_큰_JSON_구조를_저장하고_조회할_수_있다(self, store: MiniRedisStore) -> None:
        # Given
        large = {"items": [{"id": i, "data": "x" * 100} for i in range(1000)]}

        # When
        store.set("big_json", large)
        result = store.get("big_json")

        # Then
        assert len(result["items"]) == 1000
        assert result["items"][999]["id"] == 999


# ===========================================================================
# 엣지 케이스: lazy expiration의 한계
# ===========================================================================

class TestLazyExpiration:
    def test_만료된_키도_접근하지_않으면_data에_남아있다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            for i in range(100):
                store.set(f"k{i}", "v", ttl_seconds=1)

            # When — 만료 시점이 지났지만 아무 키도 접근하지 않음
            mock_time.monotonic.return_value = base + 2

            # Then — lazy expiration이므로 아직 _data에 남아있음
            assert len(store._data) == 100

    def test_만료된_키를_하나만_접근하면_그것만_정리된다(self, store: MiniRedisStore) -> None:
        # Given
        base = 1000.0
        with patch("core.time") as mock_time:
            mock_time.monotonic.return_value = base
            for i in range(100):
                store.set(f"k{i}", "v", ttl_seconds=1)

            mock_time.monotonic.return_value = base + 2

            # When — 하나만 접근
            store.get("k0")

            # Then — 접근한 것만 정리됨
            assert len(store._data) == 99
