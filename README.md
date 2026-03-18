# Minimi

> Minimi is Mini My In-Memory

이 저장소는 두 개의 Python 프로젝트와 `k6` 스크립트를 함께 담고 있다.

- `miniredis`: JSON key-value 저장과 set 시 TTL 설정을 지원하는 Mini Redis HTTP API
- `demo-app`: 비싼 랭킹 계산 조회와 캐시 조회를 비교하는 FastAPI 데모 앱
- `k6`: demo-app 캐시 성능과 MiniRedis 동시성 시나리오를 재현하는 부하 테스트 스크립트

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

## 프로젝트 역할

### `miniredis`

- 문자열 key와 JSON value를 다루는 Mini Redis HTTP API
- `set/get/delete/exists/incr/expire/ttl/cleanup_expired` 제공
- `set` 요청의 `ttl_seconds`로 lazy expiration TTL을 설정할 수 있다

### `demo-app`

- FastAPI 기반 캐시 데모 앱
- `demo-app/main.py`가 API와 `MiniRedisClient`를 담당
- `demo-app/db.py`가 1000개 상품 후보를 읽고 랭킹 점수를 계산하는 느린 DB 시뮬레이션을 담당
- `demo-app/dashboard.py`가 실시간 메트릭과 k6 결과 시각화를 담당
- 주요 엔드포인트
  - `GET /`
  - `GET /dashboard-data`
  - `GET /health`
  - `GET /ranking-direct`
  - `GET /ranking-cache`
  - `POST/GET/DELETE /demo-store`

## 데모 동작

### `GET /ranking-direct`

- 매 요청마다 상품 후보 1000개를 읽는다.
- 조회수, 좋아요, 위시리스트, 판매량, 리뷰 수, 재구매 지표, 출시 후 경과일을 합쳐 점수를 계산한다.
- 점수가 높은 순으로 상위 10개를 정렬해 반환한다.
- `demo-app/db.py`에서 100~200ms 인위적 지연을 준다.
- 캐시는 사용하지 않는다.

### `GET /ranking-cache`

- 먼저 `miniredis`에서 `ranking:top10` 키를 조회한다.
- cache hit면 저장된 top 10을 바로 반환한다.
- cache miss면 `ranking-direct`와 같은 계산을 수행한 뒤 TTL 5초로 저장한다.
- 동시 miss 때는 demo-app 내부 lock으로 한 번만 재계산해서 캐시 stampede를 줄인다.
- `demo-app` 로그에서 `cache hit` / `cache miss`를 확인할 수 있다.

### `GET /`

- demo-app 대시보드 페이지다.
- 실시간 요청 수, 평균 응답 시간, p95, cache hit/miss 비율을 보여준다.
- 마지막 `k6` 실행 결과 파일 `demo-app/perf-results/latest.json` 을 읽어 카드와 비교 바 형태로 보여준다.
- 페이지 안에서 `MiniRedis` 저장/조회/삭제도 직접 시연할 수 있다.
- playground에서는 TTL을 저장 시에만 설정하며, 남은 TTL은 별도로 표시하지 않는다.

## 실행 방법

### Docker

```bash
docker compose up --build
```

- `demo-app`: `http://localhost:8001`
- `miniredis`: `http://localhost:8000`

### Docker 없이 로컬 실행

터미널 1:

```bash
cd miniredis
uv run uvicorn server:app --host 127.0.0.1 --port 8000
```

터미널 2:

```bash
cd demo-app
uv run uvicorn main:app --host 127.0.0.1 --port 8001
```

브라우저:

```bash
http://127.0.0.1:8001
```

예시 호출:

```bash
curl "http://127.0.0.1:8001/ranking-direct"
curl "http://127.0.0.1:8001/ranking-cache"
curl "http://127.0.0.1:8001/ranking-cache"
sleep 6
curl "http://127.0.0.1:8001/ranking-cache"
```

로그 확인:

```bash
docker compose logs -f demo-app
```

또는 로컬 실행 터미널에서 바로 확인한다.

## `k6` 실행 방법

서비스를 띄운 뒤 로컬에서 실행한다.

### demo-app 캐시 시나리오

- `ranking-cache`: 100 VUs로 10초 동안 `GET /ranking-cache`
- `ranking-direct`: 100 VUs로 10초 동안 `GET /ranking-direct`

스크립트는 cache 경로를 먼저 실행하고, 결과 JSON을 `demo-app/perf-results/latest.json` 에 저장한다.
demo-app 대시보드는 이 파일을 2초마다 다시 읽어 화면에 자동 반영한다.
이 파일은 실행 산출물이며 기본 커밋 대상에서는 제외한다.

```bash
k6 run k6/basic.js
```

환경 변수를 써서 대상 주소를 바꿀 수도 있다.

```bash
DEMO_APP_BASE_URL=http://localhost:8001 k6 run k6/basic.js
```

주요 지표:

- `ranking_direct_duration`: 평균 응답 시간과 `p(95)`
- `ranking_cache_duration`: 평균 응답 시간과 `p(95)`
- `ranking_direct_requests`: 총 요청 수와 초당 처리량(rate)
- `ranking_cache_requests`: 총 요청 수와 초당 처리량(rate)
- `ranking_direct_failures`: 실패율
- `ranking_cache_failures`: 실패율

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

API로 직접 확인하려면:

```bash
curl -X POST http://localhost:8001/demo-store \
  -H "Content-Type: application/json" \
  -d '{"key":"demo:manual:ranking","value":{"feature":"manual demo","catalog_size":1000,"top_n":10},"ttl_seconds":30}'

curl "http://localhost:8001/demo-store?key=demo:manual:ranking"

curl -X DELETE "http://localhost:8001/demo-store?key=demo:manual:ranking"
```

## 결과 해석

- `ranking-direct`는 모든 요청이 100~200ms 지연과 1000개 후보 점수 계산을 직접 맞기 때문에 평균 응답 시간과 p95가 높게 나와야 정상이다.
- `ranking-cache`는 초반 miss와 TTL 만료 구간 일부 요청만 느리고, 대부분은 hit이므로 평균 응답 시간과 p95가 더 낮아져야 정상이다.
- `ranking_cache_requests`의 rate가 `ranking_direct_requests`보다 높으면 같은 시간에 더 많은 요청을 처리했다는 뜻이다.
- 실패율이 0에 가깝고 latency 차이가 뚜렷하면 캐시 효과가 잘 재현된 것이다.

## 검증

예시 검증 명령:

```bash
cd miniredis
uv run pytest tests/test_core.py tests/test_server.py
```

## 참고

- `ex_Dockerfile`은 실제 Dockerfile 작성 기준으로 유지한다.
- `miniredis/server.py`, `miniredis/core.py`, `miniredis/protocol.py`는 세 파일 합산 1000줄 이하를 목표로 유지한다.
- `uv.lock`은 의존성 잠금 파일이며 라인 수 제한에서 제외한다.
