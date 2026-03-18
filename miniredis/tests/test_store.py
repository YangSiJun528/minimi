from __future__ import annotations

import inspect
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import MiniRedisStore


class FakeClock:
    def __init__(self, current: float = 0.0) -> None:
        self._current = current
        self._lock = threading.Lock()

    def __call__(self) -> float:
        with self._lock:
            return self._current

    def time(self) -> float:
        return self()

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._current += seconds


def build_store(clock: FakeClock | None = None) -> MiniRedisStore:
    parameters = inspect.signature(MiniRedisStore).parameters
    if clock is not None and "clock" in parameters:
        return MiniRedisStore(clock=clock.time)
    return MiniRedisStore()


def test_set_get_delete_roundtrip() -> None:
    store = build_store()

    store.set("user:1", {"name": "mini", "age": 7})

    assert store.get("user:1") == {"name": "mini", "age": 7}
    assert store.delete("user:1") is True
    assert store.get("user:1") is None


def test_exists_for_present_and_missing_keys() -> None:
    store = build_store()

    store.set("present", "value")

    assert store.exists("present") is True
    assert store.exists("missing") is False


def test_missing_key_returns_none_and_false() -> None:
    store = build_store()

    assert store.get("missing") is None
    assert store.delete("missing") is False
    assert store.exists("missing") is False


def test_overwrite_replaces_existing_value() -> None:
    store = build_store()

    store.set("config", {"version": 1})
    store.set("config", {"version": 2})

    assert store.get("config") == {"version": 2}


def test_ttl_expiration_removes_value() -> None:
    clock = FakeClock()
    store = build_store(clock)

    store.set("session", {"active": True}, ttl_seconds=1)

    assert store.get("session") == {"active": True}

    if "clock" in inspect.signature(MiniRedisStore).parameters:
        clock.advance(1.1)
    else:
        time.sleep(1.1)

    assert store.get("session") is None
    assert store.exists("session") is False


def test_ttl_reports_remaining_time_when_supported() -> None:
    clock = FakeClock()
    store = build_store(clock)

    ttl_method = getattr(store, "ttl", None)
    if ttl_method is None:
        pytest.skip("MiniRedisStore.ttl() is not implemented yet.")

    store.set("token", "abc", ttl_seconds=3)

    remaining = ttl_method("token")
    assert remaining is not None
    assert remaining > 0


def test_concurrent_set_operations_keep_all_keys_consistent() -> None:
    store = build_store()

    def writer(index: int) -> None:
        store.set(f"user:{index}", {"id": index})

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(writer, range(100)))

    for index in range(100):
        assert store.get(f"user:{index}") == {"id": index}


def test_concurrent_overwrite_keeps_value_valid() -> None:
    store = build_store()

    def writer(index: int) -> None:
        store.set("shared", {"version": index})

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(writer, range(50)))

    final_value = store.get("shared")
    assert isinstance(final_value, dict)
    assert "version" in final_value
    assert 0 <= final_value["version"] < 50
