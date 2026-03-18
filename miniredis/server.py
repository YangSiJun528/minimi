from time import sleep

from fastapi import FastAPI, Query

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


@app.get("/db-direct")
async def db_direct(record_id: int = Query(..., alias="id", ge=1)) -> dict[str, int | str | bool]:
    record = _fake_db_lookup(record_id)
    return {
        **record,
        "source": "db",
        "cache_hit": False,
    }


@app.get("/cache")
async def cache_lookup(record_id: int = Query(..., alias="id", ge=1)) -> dict[str, int | str | bool]:
    cache_key = f"user:{record_id}"
    cached = store.get(cache_key)
    if cached is not None:
        return {
            **cached,
            "source": "cache",
            "cache_hit": True,
        }

    record = _fake_db_lookup(record_id)
    store.set(cache_key, record, ttl_seconds=30)
    return {
        **record,
        "source": "db",
        "cache_hit": False,
    }


@app.get("/get", response_model=GetResponse)
async def get_value_for_benchmark(key: str = Query(..., min_length=1)) -> GetResponse:
    value = store.get(key)
    found = value is not None
    return GetResponse(
        success=True,
        message=None if found else f"Key '{key}' not found",
        key=key,
        value=value,
        found=found,
    )


@app.delete("/delete", response_model=BaseResponse)
async def delete_value_for_benchmark(key: str = Query(..., min_length=1)) -> BaseResponse:
    deleted = store.delete(key)
    return BaseResponse(
        success=deleted,
        message=f"Deleted key '{key}'" if deleted else f"Key '{key}' not found",
    )


@app.get("/exists", response_model=ExistsResponse)
async def exists_value_for_benchmark(key: str = Query(..., min_length=1)) -> ExistsResponse:
    exists = store.exists(key)
    return ExistsResponse(
        success=True,
        message=None,
        key=key,
        exists=exists,
    )
