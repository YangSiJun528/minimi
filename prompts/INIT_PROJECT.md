# Mini Redis + Demo Project Scaffold Prompt

제공된 자료를 기반으로 **두 개의 별도 프로젝트가 함께 들어 있는 저장소 형태**로 기본 골격을 생성해줘.

1. `miniredis`: 과제 제출용 Mini Redis 프로젝트
2. `demo-app`: 시연용 프로젝트

두 프로젝트는 **같은 저장소 내부에 공존**하지만, **`demo-app`은 `miniredis` 내부에 포함되면 안 된다.**
즉, 루트 기준으로 서로 분리된 디렉토리여야 한다.

구현 목적은 **구조 설계와 인터페이스 정의**에 있으며, **실제 내부 구현은 작성하지 않는다.**
함수와 메서드의 본문은 모두 `pass`로 두고, 테스트 파일은 **예시 파일만 생성**하며 테스트 함수 본문조차 넣지 않는다.

---

## 전체 제약

* 전체 코드 라인 수는 **1000줄 이하**
* Python 기반
* HTTP API + JSON 통신 구조
* 요청/응답 모델은 **Pydantic 사용**
* 테스트는 **pytest 기준**
* `k6` 예시 스크립트 포함
* Docker / Docker Compose 기반 실행 예시 포함
* README 포함

---

## 1. `miniredis` 프로젝트 요구사항

### 목적

HTTP API 기반의 Mini Redis 프로젝트 골격 생성

### 구성 파일

* `server.py`
* `core.py`
* `protocol.py`

---

### 파일별 역할

#### `protocol.py`

* HTTP API에서 사용하는 JSON 요청/응답 모델을 **Pydantic 기반**으로 정의
* key/value 관련 요청 모델
* TTL 관련 요청 모델
* 공통 응답 모델
* JSON value 타입 별칭 정의

---

#### `core.py`

* 핵심 기능 인터페이스 정의
* Python 내장 `dict` 기반 key-value 저장소를 전제로 한 구조
* 아래 기능의 함수/메서드 시그니처만 선언하고 내부는 모두 `pass`

  * `set`
  * `get`
  * `delete`
  * `expire`
  * `ttl`
  * `exists`
  * `cleanup_expired`

---

#### `server.py`

* HTTP API 엔드포인트만 정의
* 요청을 받아 `core.py`를 호출하는 구조만 잡기
* 각 핸들러 함수 내부는 모두 `pass`
* 외부에서 사용할 수 있는 Mini Redis API 형태로 구성

---

### 타입 제약

* key는 **문자열(`str`)만 허용**
* value는 **JSON 타입만 허용**

Python 기준 허용 범위:

* `dict`
* `list`
* `str`
* `int`
* `float`
* `bool`
* `None`

허용하지 않음:

* 사용자 정의 객체
* 바이너리 데이터
* 클래스 인스턴스

---

### 테스트

* `pytest` 기준의 테스트 디렉토리 구조만 생성
* 테스트 파일은 **초기 빈 예시 파일만 생성**
* 테스트 함수, 클래스, `pass`, assert 등 **어떤 코드도 작성하지 말 것**

예:

```
tests/
  test_core.py
  test_server.py
```

---

### Docker

* `uv` 기반 실행을 고려한 프로젝트 구조
* Docker로 실행 가능하도록 `Dockerfile` 추가
* `ex_Dockerfile` 참고 가능한 형태

---

## 2. `demo-app` 프로젝트 요구사항

### 목적

시연용 프로젝트 골격 생성

---

### 조건

* `FastAPI` 기반
* `MongoDB` 사용 전제
* 사용자가 만든 **Mini Redis API 호출 구조 포함**
* 내부 구현은 필요 없음
* 모든 함수/메서드 본문은 `pass`

---

### 요구사항

* `demo-app`은 `miniredis`와 동일 루트에 존재
* 절대 `miniredis` 내부에 포함되면 안 됨

구성 예시:

* FastAPI 진입 파일
* MongoDB 연동 모듈
* Mini Redis API 클라이언트 모듈
* 요청/응답 모델 파일

---

### Docker Compose

* `docker-compose.yml` 포함
* 구성:

  * demo-app
  * MongoDB
  * (선택) miniredis 연동 예시

---

## 3. `k6` 예시 스크립트

* 별도 폴더에 저장

예:

```
k6/
  basic.js
```

요구사항:

* 매우 단순한 스크립트
* 더미 API에 요청 **1번만 수행**
* 복잡한 부하 테스트 필요 없음

---

## 4. README 요구사항

루트 `README.md`에 아래 내용을 포함

### 필수 포함 항목

1. 전체 저장소 구조 설명
2. `miniredis` 실행 방법 (Docker 기반)
3. `demo-app` 실행 방법 (Docker Compose 기반)
4. `k6` 실행 방법
5. 각 프로젝트 역할 설명
6. 현재 상태가 **골격만 있고 내부 구현은 비어 있음**을 명시

---

## 출력 형식

* 먼저 **루트 기준 디렉토리 구조** 출력
* 이후 각 파일 코드 순서대로 출력
* 설명은 최소화하고 코드 중심으로 작성

---

## 매우 중요한 제약

* 모든 함수/메서드 본문은 반드시 `pass`
* 테스트 파일은 **완전히 빈 파일**
* `demo-app`은 `miniredis` 내부에 포함되면 안 됨
* 실제 비즈니스 로직, DB 로직, HTTP 처리 로직 구현 금지
