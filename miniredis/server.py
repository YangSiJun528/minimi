from fastapi import FastAPI

from core import MiniRedisStore
from protocol import (
    BaseResponse,
    ExistsResponse,
    ExpireRequest,
    GetResponse,
    SetRequest,
    TTLResponse,
)

app = FastAPI(title="Mini Redis")
store = MiniRedisStore()


@app.get("/health", response_model=BaseResponse)
async def healthcheck() -> BaseResponse:
    return BaseResponse(success=True, message="ok")


@app.post("/set", response_model=BaseResponse)
async def set_value(request: SetRequest) -> BaseResponse:
    store.set(request.key, request.value, request.ttl_seconds)
    return BaseResponse(success=True, message="ok")


@app.get("/get", response_model=GetResponse)
async def get_value(key: str) -> GetResponse:
    if not store.exists(key):
        return GetResponse(success=False, key=key, value=None, found=False, message="not found")
    value = store.get(key)
    return GetResponse(success=True, key=key, value=value, found=True, message="ok")


@app.delete("/delete", response_model=BaseResponse)
async def delete_value(key: str) -> BaseResponse:
    deleted = store.delete(key)
    return BaseResponse(success=deleted, message="deleted" if deleted else "not found")


@app.get("/exists", response_model=ExistsResponse)
async def exists_value(key: str) -> ExistsResponse:
    exists = store.exists(key)
    return ExistsResponse(success=exists, key=key, exists=exists)


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
