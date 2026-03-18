import sys
from pathlib import Path
import asyncio

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from protocol import ExpireRequest, KeyRequest, SetRequest
from server import cleanup_expired, delete_value, exists_value, expire_value, get_value, healthcheck, set_value, ttl_value


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clear_store():
    from server import store

    store._store.clear()
    yield
    store._store.clear()


def test_healthcheck() -> None:
    response = run(healthcheck())
    assert response.success is True
    assert response.message == "ok"


def test_set_get_delete_exists_flow() -> None:
    created = run(set_value(SetRequest(key="k", value={"a": 1})))
    assert created.success is True

    got = run(get_value(KeyRequest(key="k")))
    assert got.success is True
    assert got.found is True
    assert got.key == "k"
    assert got.value == {"a": 1}

    exists = run(exists_value(KeyRequest(key="k")))
    assert exists.success is True
    assert exists.exists is True

    deleted = run(delete_value(KeyRequest(key="k")))
    assert deleted.success is True
    assert deleted.message == "deleted"

    not_exists = run(exists_value(KeyRequest(key="k")))
    assert not_exists.success is False
    assert not_exists.exists is False


def test_ttl_expiry_and_cleanup() -> None:
    created = run(set_value(SetRequest(key="t", value="x", ttl_seconds=1)))
    assert created.success is True

    ttl = run(ttl_value(KeyRequest(key="t")))
    assert ttl.success is True
    assert ttl.found is True
    assert isinstance(ttl.ttl_seconds, int)
    assert ttl.ttl_seconds >= 0

    from time import sleep

    sleep(1.1)
    after = run(get_value(KeyRequest(key="t")))
    assert after.found is False

    cleaned = run(cleanup_expired())
    assert cleaned.success is True
    assert "cleaned=" in cleaned.message


def test_expire_extension() -> None:
    run(set_value(SetRequest(key="e", value="z")))

    ok = run(expire_value(ExpireRequest(key="e", ttl_seconds=2)))
    assert ok.success is True

    ttl = run(ttl_value(KeyRequest(key="e")))
    assert ttl.ttl_seconds is not None
    assert ttl.ttl_seconds >= 1
