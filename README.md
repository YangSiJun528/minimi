# Minimi

> Minimi is Mini My In-Memory

이 저장소는 두 개의 별도 Python 프로젝트를 함께 담는 골격 저장소다.

- `miniredis`: 과제 제출용 Mini Redis HTTP API 골격
- `demo-app`: MongoDB와 Mini Redis 연동 구조만 보여주는 시연용 FastAPI 골격

현재 상태는 구현이 아닌 구조 설계 단계다. 함수와 메서드 본문은 모두 `pass`이며, 테스트 파일도 예시용 빈 파일만 포함한다.

## 저장소 구조

```text
.
├── README.md
├── docker-compose.yml
├── ex_Dockerfile
├── k6/
│   └── basic.js
├── miniredis/
│   ├── Dockerfile
│   ├── core.py
│   ├── protocol.py
│   ├── pyproject.toml
│   ├── server.py
│   ├── tests/
│   │   ├── test_core.py
│   │   └── test_server.py
│   └── uv.lock
└── demo-app/
    ├── Dockerfile
    ├── main.py
    ├── pyproject.toml
    └── uv.lock
```

## 프로젝트 역할

### `miniredis`

- 문자열 key와 JSON value를 다루는 Mini Redis HTTP API 골격
- 요청/응답 모델은 Pydantic 기반으로 정의
- 내부 저장소와 TTL 로직은 인터페이스만 선언

### `demo-app`

- FastAPI 기반 시연용 서비스 골격
- MongoDB 연결 구조와 Mini Redis HTTP 호출 구조만 노출
- 도메인 API는 아직 정하지 않았고, 현재는 헬스체크만 제공

## `miniredis` 실행 방법

```bash
docker build -t miniredis-app ./miniredis
docker run --rm -p 8000:8000 miniredis-app
```

## `demo-app` 실행 방법

```bash
docker compose up --build
```

- `demo-app`: `http://localhost:8001`
- `miniredis`: `http://localhost:8000`
- `mongodb`: `mongodb://localhost:27017`

## `k6` 실행 방법

`docker compose up --build`로 서비스를 띄운 뒤 로컬에서 실행한다.

`k6`가 설치되어 있지 않다면 먼저 설치한 뒤 실행한다. 기본 스크립트는 `demo-app`의 `http://localhost:8001/health`를 호출한다.

```bash
k6 run k6/basic.js
```

## 참고

- `ex_Dockerfile`은 실제 Dockerfile 작성 기준으로 유지한다.
- `miniredis/server.py`, `miniredis/core.py`, `miniredis/protocol.py`는 향후 실제 구현 시 세 파일 합산 1000줄 이하를 목표로 한다.
- `uv.lock`은 의존성 잠금 파일이며 라인 수 제한에서 제외한다.
