import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress

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

DEFAULT_CLEANUP_INTERVAL_SECONDS = 10.0
logger = logging.getLogger(__name__)
SleepFn = Callable[[float], Awaitable[None]]

store = MiniRedisStore()


def get_cleanup_interval_seconds() -> float:
    raw_value = os.getenv("MINIREDIS_CLEANUP_INTERVAL_SECONDS")
    if raw_value is None:
        return DEFAULT_CLEANUP_INTERVAL_SECONDS

    try:
        interval_seconds = float(raw_value)
    except ValueError as exc:
        raise RuntimeError("MINIREDIS_CLEANUP_INTERVAL_SECONDS must be a positive number") from exc

    if interval_seconds <= 0:
        raise RuntimeError("MINIREDIS_CLEANUP_INTERVAL_SECONDS must be a positive number")

    return interval_seconds


def cleanup_expired_once(target_store: MiniRedisStore) -> int:
    return target_store.cleanup_expired()


async def cleanup_expired_periodically(
    target_store: MiniRedisStore,
    interval_seconds: float,
    sleep_fn: SleepFn = asyncio.sleep,
) -> None:
    while True:
        await sleep_fn(interval_seconds)
        removed = cleanup_expired_once(target_store)
        if removed > 0:
            logger.info("cleaned expired keys removed=%s", removed)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    interval_seconds = get_cleanup_interval_seconds()
    logger.info("starting ttl cleanup loop interval_seconds=%s", interval_seconds)
    cleanup_task = asyncio.create_task(
        cleanup_expired_periodically(store, interval_seconds),
        name="miniredis-ttl-cleanup",
    )

    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task


app = FastAPI(title="Mini Redis", lifespan=lifespan)


@app.get("/health", response_model=BaseResponse)
def healthcheck() -> BaseResponse:
    return BaseResponse(success=True, message="ok")


@app.post("/set", response_model=BaseResponse)
def set_value(request: SetRequest) -> BaseResponse:
    store.set(request.key, request.value, request.ttl_seconds)
    return BaseResponse(success=True, message="ok")


@app.get("/get", response_model=GetResponse)
def get_value(key: str) -> GetResponse:
    if not store.exists(key):
        return GetResponse(success=False, key=key, value=None, found=False, message="not found")
    value = store.get(key)
    return GetResponse(success=True, key=key, value=value, found=True, message="ok")


@app.delete("/delete", response_model=BaseResponse)
def delete_value(key: str) -> BaseResponse:
    deleted = store.delete(key)
    return BaseResponse(success=deleted, message="deleted" if deleted else "not found")


@app.get("/exists", response_model=ExistsResponse)
def exists_value(key: str) -> ExistsResponse:
    exists = store.exists(key)
    return ExistsResponse(success=exists, key=key, exists=exists)


@app.post("/incr", response_model=IncrResponse)
def incr_value(request: KeyRequest) -> IncrResponse:
    value = store.incr(request.key)
    return IncrResponse(success=True, key=request.key, value=value, message="ok")


@app.patch("/expire", response_model=BaseResponse)
def expire_value(request: ExpireRequest) -> BaseResponse:
    updated = store.expire(request.key, request.ttl_seconds)
    return BaseResponse(success=updated, message="ok" if updated else "not found")


@app.get("/ttl", response_model=TTLResponse)
def ttl_value(key: str) -> TTLResponse:
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
def cleanup_expired_endpoint() -> BaseResponse:
    removed = cleanup_expired_once(store)
    return BaseResponse(success=True, message=f"cleaned {removed} expired keys")
