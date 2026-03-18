from __future__ import annotations

import inspect
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import server
from core import MiniRedisStore


def _build_store() -> MiniRedisStore:
    parameters = inspect.signature(MiniRedisStore).parameters
    if "clock" in parameters:
        return MiniRedisStore(clock=time.time)
    return MiniRedisStore()


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(server, "store", _build_store())
    return TestClient(server.app)


def _paths(app) -> set[str]:
    return {route.path for route in app.routes}


def test_set_get_delete_flow(client: TestClient) -> None:
    set_response = client.post(
        "/set",
        json={"key": "user:1", "value": {"name": "mini"}, "ttl_seconds": 5},
    )
    assert set_response.status_code == 200

    get_response = client.get("/get", params={"key": "user:1"})
    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["found"] is True
    assert get_payload["value"] == {"name": "mini"}

    delete_response = client.delete("/delete", params={"key": "user:1"})
    assert delete_response.status_code == 200

    get_after_delete = client.get("/get", params={"key": "user:1"})
    assert get_after_delete.status_code == 200
    assert get_after_delete.json()["found"] is False


def test_exists_endpoint(client: TestClient) -> None:
    client.post("/set", json={"key": "feature", "value": True})

    exists_response = client.get("/exists", params={"key": "feature"})
    assert exists_response.status_code == 200
    assert exists_response.json()["exists"] is True

    missing_response = client.get("/exists", params={"key": "missing"})
    assert missing_response.status_code == 200
    assert missing_response.json()["exists"] is False


def test_invalid_input_returns_client_error(client: TestClient) -> None:
    missing_key_response = client.post("/set", json={"value": {"name": "mini"}})
    assert missing_key_response.status_code in {400, 422}

    invalid_ttl_response = client.post(
        "/set",
        json={"key": "broken", "value": "x", "ttl_seconds": 0},
    )
    assert invalid_ttl_response.status_code in {400, 422}


def test_missing_key_lookup_returns_not_found_payload(client: TestClient) -> None:
    response = client.get("/get", params={"key": "unknown"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["found"] is False
    assert payload["value"] is None


def test_ttl_expired_key_is_not_returned(client: TestClient) -> None:
    response = client.post(
        "/set",
        json={"key": "ephemeral", "value": "temp", "ttl_seconds": 1},
    )
    assert response.status_code == 200

    time.sleep(1.1)
    expired_response = client.get("/get", params={"key": "ephemeral"})

    assert expired_response.status_code == 200
    assert expired_response.json()["found"] is False


def test_overwrite_flow_returns_latest_value(client: TestClient) -> None:
    client.post("/set", json={"key": "profile", "value": {"name": "old"}})
    client.post("/set", json={"key": "profile", "value": {"name": "new"}})

    response = client.get("/get", params={"key": "profile"})

    assert response.status_code == 200
    assert response.json()["value"] == {"name": "new"}


@pytest.mark.skipif(
    "/cache" not in _paths(server.app) or "/db-direct" not in _paths(server.app),
    reason="Cache integration endpoints are not implemented on the app yet.",
)
def test_cache_miss_then_hit_flow(client: TestClient) -> None:
    first_response = client.get("/cache", params={"id": 1})
    second_response = client.get("/cache", params={"id": 1})

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    first_payload = first_response.json()
    second_payload = second_response.json()

    assert first_payload["id"] == 1
    assert second_payload["id"] == 1
    assert first_payload["name"] == second_payload["name"]
    assert first_payload["email"] == second_payload["email"]
    assert first_payload.get("cache_hit") in {False, 0, None}
    assert second_payload.get("cache_hit") in {True, 1}
    assert first_payload.get("source") == "db"
    assert second_payload.get("source") == "cache"


@pytest.mark.skipif(
    "/cache" not in _paths(server.app) or "/db-direct" not in _paths(server.app),
    reason="Cache integration endpoints are not implemented on the app yet.",
)
def test_db_direct_and_cache_return_same_record(client: TestClient) -> None:
    db_response = client.get("/db-direct", params={"id": 1})
    cache_response = client.get("/cache", params={"id": 1})

    assert db_response.status_code == 200
    assert cache_response.status_code == 200
    assert db_response.json()["id"] == cache_response.json()["id"]
