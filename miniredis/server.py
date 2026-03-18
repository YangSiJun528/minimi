from fastapi import FastAPI

from core import MiniRedisStore
from protocol import (
    BaseResponse,
    ExistsResponse,
    ExpireRequest,
    GetResponse,
    IncrResponse,
    KeyRequest,
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


@app.post("/incr", response_model=IncrResponse)
async def incr_value(request: KeyRequest) -> IncrResponse:
    try:
        value = store.incr(request.key)
    except ValueError as exc:
        return IncrResponse(success=False, key=request.key, value=None, message=str(exc))
    return IncrResponse(success=True, key=request.key, value=value, message="ok")


@app.patch("/expire", response_model=BaseResponse)
async def expire_value(request: ExpireRequest) -> BaseResponse:
    updated = store.expire(request.key, request.ttl_seconds)
    return BaseResponse(success=updated, message="ok" if updated else "not found")


@app.get("/ttl", response_model=TTLResponse)
async def ttl_value(key: str) -> TTLResponse:
    ttl_seconds = store.ttl(key)
    if ttl_seconds is None and not store.exists(key):
        return TTLResponse(success=False, key=key, ttl_seconds=None, found=False, message="not found")
    return TTLResponse(
        success=True,
        key=key,
        ttl_seconds=ttl_seconds,
        found=True,
        message="ok" if ttl_seconds is not None else "no expiration",
    )


@app.post("/cleanup_expired", response_model=BaseResponse)
async def cleanup_expired() -> BaseResponse:
    removed = store.cleanup_expired()
    return BaseResponse(success=True, message=f"cleaned {removed} expired keys")
