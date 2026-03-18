from fastapi import FastAPI

from core import MiniRedisStore
from protocol import (
    BaseResponse,
    ExistsResponse,
    ExpireRequest,
    GetResponse,
    KeyRequest,
    SetRequest,
    TTLResponse,
)

app = FastAPI(title="Mini Redis")
store = MiniRedisStore()
FAKE_DB_DELAY_SECONDS = 0.2


def _fake_db_lookup(record_id: int) -> dict[str, int | str]:
    sleep(FAKE_DB_DELAY_SECONDS)
    return {
        "id": record_id,
        "name": f"user-{record_id}",
        "email": f"user-{record_id}@example.com",
    }


@app.get("/health", response_model=BaseResponse)
async def healthcheck() -> BaseResponse:
    return BaseResponse(success=True, message="ok")


@app.post("/set", response_model=BaseResponse)
async def set_value(request: SetRequest) -> BaseResponse:
    store.set(request.key, request.value, request.ttl_seconds)
    return BaseResponse(success=True, message="ok")


@app.post("/get", response_model=GetResponse)
async def get_value(request: KeyRequest) -> GetResponse:
    if not store.exists(request.key):
        return GetResponse(success=False, key=request.key, value=None, found=False, message="not found")
    value = store.get(request.key)
    return GetResponse(success=True, key=request.key, value=value, found=True, message="ok")


@app.post("/delete", response_model=BaseResponse)
async def delete_value(request: KeyRequest) -> BaseResponse:
    deleted = store.delete(request.key)
    return BaseResponse(success=deleted, message="deleted" if deleted else "not found")


@app.post("/exists", response_model=ExistsResponse)
async def exists_value(request: KeyRequest) -> ExistsResponse:
    exists = store.exists(request.key)
    return ExistsResponse(success=exists, key=request.key, exists=exists)


# @app.post("/expire", response_model=BaseResponse)
# async def expire_value(request: ExpireRequest) -> BaseResponse:
#     # TODO: expire 기능은 다음 단계에서 구현한다.
#     pass


# @app.post("/ttl", response_model=TTLResponse)
# async def ttl_value(request: KeyRequest) -> TTLResponse:
#     # TODO: ttl 기능은 다음 단계에서 구현한다.
#     pass


# @app.post("/cleanup_expired", response_model=BaseResponse)
# async def cleanup_expired() -> BaseResponse:
#     # TODO: cleanup_expired 기능은 다음 단계에서 구현한다.
#     pass
