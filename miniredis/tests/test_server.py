import json
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def base_url() -> str:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=PROJECT_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    else:
        process.terminate()
        raise RuntimeError("mini redis server did not start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except Exception:
            process.kill()


@pytest.fixture
def unique_key() -> str:
    return f"test-{uuid.uuid4().hex}"


def request_json(url: str, method: str, path: str, payload: dict | None = None) -> dict:
    full_url = f"{url}{path}"
    headers: dict[str, str] = {}
    data = None

    if payload and method in {"GET", "DELETE"}:
        query = urllib.parse.urlencode(payload)
        full_url = f"{full_url}?{query}"
    elif payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(full_url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, path: str, payload: dict | None = None) -> dict:
    return request_json(url, "GET", path, payload)


def post_json(url: str, path: str, payload: dict | None = None) -> dict:
    return request_json(url, "POST", path, payload)


def patch_json(url: str, path: str, payload: dict) -> dict:
    return request_json(url, "PATCH", path, payload)


def delete_json(url: str, path: str, payload: dict) -> dict:
    return request_json(url, "DELETE", path, payload)


def test_헬스체크_성공(base_url: str) -> None:
    result = get_json(base_url, "/health")

    assert result["success"] is True
    assert result["message"] == "ok"


def test_set_get_exists_delete_흐름(base_url: str, unique_key: str) -> None:
    created = post_json(base_url, "/set", {"key": unique_key, "value": {"a": 1}})
    got = get_json(base_url, "/get", {"key": unique_key})
    exists = get_json(base_url, "/exists", {"key": unique_key})
    deleted = delete_json(base_url, "/delete", {"key": unique_key})
    not_exists = get_json(base_url, "/exists", {"key": unique_key})

    assert created["success"] is True

    assert got["success"] is True
    assert got["found"] is True
    assert got["key"] == unique_key
    assert got["value"] == {"a": 1}

    assert exists["success"] is True
    assert exists["exists"] is True

    assert deleted["success"] is True
    assert deleted["message"] == "deleted"

    assert not_exists["success"] is False
    assert not_exists["exists"] is False


def test_incr가_없는_키에서_시작해_누적된다(base_url: str, unique_key: str) -> None:
    first = post_json(base_url, "/incr", {"key": unique_key})
    second = post_json(base_url, "/incr", {"key": unique_key})
    got = get_json(base_url, "/get", {"key": unique_key})

    assert first["success"] is True
    assert first["value"] == 1

    assert second["success"] is True
    assert second["value"] == 2

    assert got["success"] is True
    assert got["value"] == 2


def test_expire와_ttl이_만료를_반영한다(base_url: str, unique_key: str) -> None:
    created = post_json(base_url, "/set", {"key": unique_key, "value": "value"})
    expired = patch_json(base_url, "/expire", {"key": unique_key, "ttl_seconds": 1})
    ttl_before = get_json(base_url, "/ttl", {"key": unique_key})

    time.sleep(1.1)

    ttl_after = get_json(base_url, "/ttl", {"key": unique_key})
    got_after = get_json(base_url, "/get", {"key": unique_key})

    assert created["success"] is True
    assert expired["success"] is True

    assert ttl_before["success"] is True
    assert ttl_before["found"] is True
    assert ttl_before["ttl_seconds"] is not None
    assert ttl_before["ttl_seconds"] >= 1

    assert ttl_after["success"] is False
    assert ttl_after["found"] is False
    assert ttl_after["ttl_seconds"] is None
    assert ttl_after["message"] == "not found"

    assert got_after["success"] is False
    assert got_after["found"] is False
    assert got_after["value"] is None


def test_cleanup_expired가_만료된_키를_정리한다(base_url: str, unique_key: str) -> None:
    created = post_json(base_url, "/set", {"key": unique_key, "value": "value", "ttl_seconds": 1})

    time.sleep(1.1)

    cleaned = post_json(base_url, "/cleanup_expired")
    got_after = get_json(base_url, "/get", {"key": unique_key})

    assert created["success"] is True

    assert cleaned["success"] is True
    assert cleaned["message"] is not None
    assert cleaned["message"].startswith("cleaned ")

    assert got_after["success"] is False
    assert got_after["found"] is False
    assert got_after["message"] == "not found"
