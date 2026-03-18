# Minimi

> Minimi is Mini My In-Memory
- `miniredis`: JSON key-value 저장과 set 시 TTL 설정을 지원하는 Mini Redis HTTP API
- `demo-app`: 캐시 없는 랭킹 조회와 캐시 조회를 비교하는 FastAPI 데모 앱
- `k6`: demo-app 캐시 성능과 MiniRedis 동시성 시나리오를 재현하는 부하 테스트 스크립트

# 📌 기술 선택 이유
### HTTP vs TCP/소켓 → HTTP 선택
- 성능 테스트 도구(k6 등)와의 **호환성이 높음**
- 구현 복잡도를 낮추고, 핵심 로직(저장소)에 집중하기 위함
  
### k6 vs Locust → k6 선택
- HTTP 부하 테스트에 최적화

###  pytest 선택 이유
- Python 환경에서 가장 널리 사용되는 테스트 프레임워크
- 단위 테스트 작성이 간단하고 가독성이 좋음
- 테스트 자동화 및 유지보수에 유리

###  4. FastAPI 선택 이유
- 요청/응답 모델을 통한 **타입 기반 검증**
- 비동기 지원 구조를 기본 제공



## 저장소 구조

```text
.
├── README.md
├── docker-compose.yml
├── k6/
│   ├── basic.js
│   └── miniredis/
│       ├── incr-concurrency.js
│       └── rmw-failure.js
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
    ├── dashboard.py
    ├── db.py
    ├── Dockerfile
    ├── main.py
    ├── perf-results/
    │   └── .gitkeep
    ├── pyproject.toml
    └── uv.lock
```

# 📌 프로젝트 역할

## 🔵 MiniRedis
> 인메모리 기반 Key-Value 저장소 (HTTP API)
### 주요 기능
- 문자열 key + JSON value 저장
- `set / get / delete / exists / incr / expire / ttl` 지원

### TTL 관리
- `set` 시 `ttl_seconds`로 만료 시간 설정
- 요청 시 lazy expiration 처리
- 백그라운드 cleanup (기본 10초 주기)

## 🟢 Demo App
> 캐시 성능 비교를 위한 FastAPI 기반 데모 서버

### 역할 분리
- `main.py`
  - API 엔드포인트 + MiniRedis 연동
- `db.py`
  - 1000개 상품 기반 **느린 mongodb 시뮬레이션 (100~200ms)**
- `dashboard.py`
  - 실시간 메트릭 및 k6 결과 시각화

### 주요 엔드포인트
- `GET /` → 대시보드
- `GET /ranking-direct` → 캐시 없이 DB 조회
- `GET /ranking-cache` → 캐시 적용 조회

## 📌 실행 방법
### Docker

```bash
docker compose up --build
```

- `demo-app`: `http://localhost:8001`
- `miniredis`: `http://localhost:8000`
- MiniRedis TTL cleanup 주기는 기본 10초이며 `MINIREDIS_CLEANUP_INTERVAL_SECONDS`로 조정할 수 있다

## k6 실행 방법

서비스를 띄운 뒤 로컬에서 실행합니다.

### demo-app 캐시 시나리오

- `ranking-cache`: 100 VUs로 10초 동안 `GET /ranking-cache`
- `ranking-direct`: 100 VUs로 10초 동안 `GET /ranking-direct`

스크립트 동작:

1. `ranking-cache` 경로를 먼저 실행
2. 결과 JSON을 `demo-app/perf-results/latest.json`에 저장
3. demo-app 대시보드는 해당 파일을 2초마다 다시 읽어 자동 반영

> ⚠️ 해당 JSON 파일은 실행 결과물이므로 기본 커밋 대상에서 제외합니다.

### 실행 명령어

```bash
k6 run k6/basic.js
```

### MiniRedis 동시성 시나리오

- MiniRedis 동시성 검증 스크립트는 `k6/miniredis/` 아래에 둔다.
- `incr-concurrency.js`는 같은 키에 `POST /incr`를 동시에 보내고 최종 값이 정확히 `VUS * ITERATIONS_PER_VU`인지 확인한다.
- `rmw-failure.js`는 클라이언트에서 `GET -> +1 -> SET`를 수행해 contention 상황의 lost update를 의도적으로 재현한다.
- `incr-concurrency.js`의 성공은 현재 단일 프로세스 `uvicorn` 실행 기준에서의 정확한 누적 검증이다.
- `rmw-failure.js`는 서버 버그를 찾는 테스트가 아니라 비원자적 read-modify-write가 왜 깨지는지 보여주는 재현 시나리오다.

MiniRedis 서버를 띄운 뒤 실행한다.

```bash
docker build -t miniredis ./miniredis
docker run --rm -p 8000:8000 miniredis
```

```bash
k6 run -e MINIREDIS_BASE_URL=http://localhost:8000 -e VUS=100 -e ITERATIONS_PER_VU=10 k6/miniredis/incr-concurrency.js
```

```bash
k6 run -e MINIREDIS_BASE_URL=http://localhost:8000 -e VUS=100 -e ITERATIONS_PER_VU=10 k6/miniredis/rmw-failure.js
```

## CRUD 시연

대시보드의 `MiniRedis Playground` 섹션에서 직접 저장/조회/삭제할 수 있다.
TTL은 저장 시에만 설정하며, 조회 응답에서 남은 TTL은 보여주지 않는다.
수동 수거가 필요하면 `POST /cleanup_expired`를 호출할 수 있다.

API로 직접 확인하려면:

```bash
curl -X POST http://localhost:8001/demo-store \
  -H "Content-Type: application/json" \
  -d '{"key":"demo:manual:ranking","value":{"feature":"manual demo","catalog_size":1000,"top_n":10},"ttl_seconds":30}'

curl "http://localhost:8001/demo-store?key=demo:manual:ranking"

curl -X DELETE "http://localhost:8001/demo-store?key=demo:manual:ranking"
```

# 📌 문제 발견 및 해결

## 문제 상황

초기 구현에서 Codex가 생성한 코드에는  
불필요한 `async/await` 사용이 과도하게 포함되어 있었다.

- 대부분의 로직이 **메모리 기반 연산 (딕셔너리 접근)**
- I/O 작업이 없기 때문에 비동기의 이점을 활용하지 못함

## 분석

비동기가 필요한 경우는 :
- TTL 만료 처리를 위한 **주기적 정리 (active cleanup)**

이 외의 작업은 모두:
- 즉시 실행되는 CPU 연산
- 동기 방식이 더 적합

## 해결
- 불필요한 `async/await` 제거
- 저장소 로직을 **동기 방식으로 단순화**
- 필요한 부분(TTL cleanup 등)에만 비동기 또는 주기 작업 적용
- 
## 📌 결과 해석

- `ranking-direct`는 모든 요청이 100~200ms 지연과 1000개 후보 점수 계산을 직접 맞기 때문에 평균 응답 시간과 p95가 높게 나와야 정상이다.
- `ranking-cache`는 초반 miss와 TTL 만료 구간 일부 요청만 느리고, 대부분은 hit이므로 평균 응답 시간과 p95가 더 낮아져야 정상이다.
- `ranking_cache_requests`의 rate가 `ranking_direct_requests`보다 높으면 같은 시간에 더 많은 요청을 처리했다는 뜻이다.
- 실패율이 0에 가깝고 latency 차이가 뚜렷하면 캐시 효과가 잘 재현된 것이다.

## 📌 검증

예시 검증 명령:

```bash
cd miniredis
uv run pytest tests/test_core.py tests/test_server.py
```

## 참고

- `ex_Dockerfile`은 실제 Dockerfile 작성 기준으로 유지한다.
- `miniredis/server.py`, `miniredis/core.py`, `miniredis/protocol.py`는 세 파일 합산 1000줄 이하를 목표로 유지한다.
- `uv.lock`은 의존성 잠금 파일이며 라인 수 제한에서 제외한다.
