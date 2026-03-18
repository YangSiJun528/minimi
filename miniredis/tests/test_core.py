import sys
from pathlib import Path
import asyncio
import time

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from core import MiniRedisStore


def test_set_get_delete_exists() -> None:
    store = MiniRedisStore()

    store.set("name", "value")
    assert store.get("name") == "value"
    assert store.exists("name") is True

    deleted = store.delete("name")
    assert deleted is True
    assert store.get("name") is None
    assert store.exists("name") is False


def test_set_with_ttl_expires() -> None:
    store = MiniRedisStore()

    store.set("temp", "x", ttl_seconds=1)
    assert store.exists("temp") is True

    time.sleep(1.1)
    assert store.get("temp") is None
    assert store.exists("temp") is False


def test_expire_and_ttl() -> None:
    store = MiniRedisStore()

    store.set("session", "abc")
    assert store.expire("session", 1) is True

    ttl = store.ttl("session")
    assert isinstance(ttl, int)
    assert ttl >= 0

    store.set("persistent", "y")
    assert store.ttl("persistent") is None


def test_cleanup_expired() -> None:
    store = MiniRedisStore()

    store.set("a", 1, ttl_seconds=1)
    store.set("b", 2, ttl_seconds=1)
    store.set("c", 3)

    time.sleep(1.1)
    cleaned = store.cleanup_expired()
    assert cleaned == 2
    assert store.exists("a") is False
    assert store.exists("b") is False
    assert store.get("c") == 3
