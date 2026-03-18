import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def base_url() -> str:
    # Given: an available local port is allocated.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Given: mini redis server is started once for the whole test session.
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
        cwd=Path(__file__).resolve().parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    # When: wait until /health responds.
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


def post_json(url: str, path: str, payload: dict) -> dict:
    # Given: a request payload is prepared.
    # When: it is sent as POST JSON.
    request = urllib.request.Request(
        f"{url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # Then: parse and return response json.
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def test_healthcheck_success(base_url: str) -> None:
    # Given: the server is running.
    # When: /health is requested.
    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
        result = json.loads(response.read().decode("utf-8"))

    # Then: it returns success.
    assert result["success"] is True
    assert result["message"] == "ok"


def test_set_get_delete_flow(base_url: str) -> None:
    # Given: start from an empty state for the key.
    # When: call endpoints for set, get, exists, and delete in order.
    created = post_json(base_url, "/set", {"key": "k", "value": {"a": 1}})
    got = post_json(base_url, "/get", {"key": "k"})
    exists = post_json(base_url, "/exists", {"key": "k"})
    deleted = post_json(base_url, "/delete", {"key": "k"})
    not_exists = post_json(base_url, "/exists", {"key": "k"})

    # Then: set/get/exists/delete flow behaves as expected.
    assert created["success"] is True

    assert got["success"] is True
    assert got["found"] is True
    assert got["key"] == "k"
    assert got["value"] == {"a": 1}

    assert exists["success"] is True
    assert exists["exists"] is True

    assert deleted["success"] is True
    assert deleted["message"] == "deleted"

    assert not_exists["success"] is False
    assert not_exists["exists"] is False
