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
    # Given: 사용 가능한 로컬 포트를 하나 확보한다.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Given: 테스트 동안 한 번만 mini redis 서버를 실행한다.
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
    # Given: JSON 본문을 준비한다.
    # When: POST 요청을 보낸다.
    request = urllib.request.Request(
        f"{url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # Then: 응답 본문을 JSON으로 파싱해 돌려준다.
    with urllib.request.urlopen(request, timeout=2) as response:
        return json.loads(response.read().decode("utf-8"))


def test_헬스체크_성공(base_url: str) -> None:
    # Given: 테스트용 서버가 실행 중이다.
    # When: HTTP로 /health를 호출한다.
    with urllib.request.urlopen(f"{base_url}/health", timeout=2) as response:
        result = json.loads(response.read().decode("utf-8"))

    # Then: 성공 응답을 받는다.
    assert result["success"] is True
    assert result["message"] == "ok"


def test_set_조회_삭제_흐름(base_url: str) -> None:
    # Given: 임시 키가 없는 빈 상태에서 시작한다.
    # When: HTTP로 set/get/exists/delete를 순차적으로 호출한다.
    created = post_json(base_url, "/set", {"key": "k", "value": {"a": 1}})
    got = post_json(base_url, "/get", {"key": "k"})
    exists = post_json(base_url, "/exists", {"key": "k"})
    deleted = post_json(base_url, "/delete", {"key": "k"})
    not_exists = post_json(base_url, "/exists", {"key": "k"})

    # Then: set/get/exists/delete가 기대대로 동작한다.
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
