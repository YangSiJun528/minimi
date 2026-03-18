from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, ValidationError

from dashboard import DemoMetricsStore, build_dashboard_html, build_dashboard_payload
from db import SlowDemoDatabase


logger = logging.getLogger("demo-app")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

CACHE_TTL_SECONDS = 5
RANKING_CACHE_KEY = "ranking:top10"
REPORT_PATH = Path(
    os.getenv("K6_SUMMARY_PATH", Path(__file__).resolve().parent / "perf-results" / "latest.json")
)


class HealthResponse(BaseModel):
    service: str
    status: str
    mongodb: str
    miniredis: str


class RankedProduct(BaseModel):
    rank: int
    product_id: str
    name: str
    brand: str
    category: str
    price_krw: int
    score: float
    views_28d: int
    likes_28d: int
    wishlists_28d: int
    sales_28d: int
    conversion_pct: float
    review_score: float
    days_since_launch: int


class RankingPayload(BaseModel):
    ranking_name: str
    algorithm_version: str
    catalog_size: int
    top_n: int
    computed_at: str
    top_products: list[RankedProduct]


class RankingResponse(BaseModel):
    key: str
    ranking: RankingPayload
    source: Literal["db", "cache"]
    cache_status: Literal["bypass", "hit", "miss"]
    cache_ttl_seconds: int | None = None
    db_delay_ms: int | None = None


class CachePlaygroundRequest(BaseModel):
    key: str
    value: Any
    ttl_seconds: int | None = Field(default=None, ge=1)


class CachePlaygroundResponse(BaseModel):
    success: bool
    operation: Literal["set", "get", "delete"]
    key: str
    exists: bool | None = None
    deleted: bool | None = None
    value: Any = None
    ttl_seconds: int | None = None
    message: str | None = None


class MongoGateway:
    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._database = SlowDemoDatabase()

    def ping(self) -> str:
        return f"ok ({self._uri})"

    def compute_ranking(self, limit: int = 10) -> tuple[dict[str, Any], int]:
        return self._database.compute_top_ranking(limit=limit)

    def preview_ranking(self, limit: int = 5) -> dict[str, Any]:
        return self._database.preview_top_ranking(limit=limit)


class MiniRedisClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=2.0)

    def _get(self, path: str) -> dict[str, Any]:
        try:
            response = self._client.get(path)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"miniredis GET {path} failed") from exc
        return response.json()

    def _post(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload or {})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"miniredis POST {path} failed") from exc
        return response.json()

    def health(self) -> str:
        payload = self._get("/health")
        return payload.get("message", "unknown")

    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        payload: dict[str, Any] = {"key": key, "value": value}
        if ttl_seconds is not None:
            payload["ttl_seconds"] = ttl_seconds
        self._post("/set", payload)

    def get(self, key: str) -> object | None:
        payload = self._post("/get", {"key": key})
        if not payload.get("found", False):
            return None
        return payload.get("value")

    def delete(self, key: str) -> bool:
        payload = self._post("/delete", {"key": key})
        return bool(payload.get("success", False))

    def exists(self, key: str) -> bool:
        payload = self._post("/exists", {"key": key})
        return bool(payload.get("exists", False))

    def close(self) -> None:
        self._client.close()


def build_cache_key() -> str:
    return RANKING_CACHE_KEY


def validate_ranking_payload(raw_payload: object) -> RankingPayload | None:
    if raw_payload is None:
        return None

    try:
        return RankingPayload.model_validate(raw_payload)
    except ValidationError:
        logger.warning("invalid cached ranking payload", exc_info=True)
        return None


app = FastAPI(title="Demo App")
mongo_gateway = MongoGateway(os.getenv("MONGODB_URI", "mongodb://localhost:27017/demoapp"))
miniredis_client = MiniRedisClient(os.getenv("MINIREDIS_BASE_URL", "http://localhost:8000"))
metrics_store = DemoMetricsStore()
ranking_cache_lock = threading.Lock()


@app.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    try:
        miniredis_status = miniredis_client.health()
    except RuntimeError as exc:
        miniredis_status = f"error ({exc})"

    return HealthResponse(
        service="demo-app",
        status="ok",
        mongodb=mongo_gateway.ping(),
        miniredis=miniredis_status,
    )


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(build_dashboard_html())


@app.get("/dashboard-data")
def dashboard_data() -> dict[str, Any]:
    return build_dashboard_payload(
        metrics_store=metrics_store,
        report_path=REPORT_PATH,
        ranking_preview=mongo_gateway.preview_ranking(limit=5),
    )


@app.get("/ranking-direct", response_model=RankingResponse)
def ranking_direct() -> RankingResponse:
    started_at = time.perf_counter()
    cache_key = build_cache_key()

    ranking, delay_ms = mongo_gateway.compute_ranking(limit=10)
    ranking_payload = RankingPayload.model_validate(ranking)

    logger.info(
        "ranking direct computed key=%s catalog_size=%s top_n=%s delay_ms=%s",
        cache_key,
        ranking_payload.catalog_size,
        ranking_payload.top_n,
        delay_ms,
    )
    metrics_store.record_ranking_direct(duration_ms=(time.perf_counter() - started_at) * 1000, success=True)
    return RankingResponse(
        key=cache_key,
        ranking=ranking_payload,
        source="db",
        cache_status="bypass",
        db_delay_ms=delay_ms,
    )


@app.get("/ranking-cache", response_model=RankingResponse)
def ranking_cache() -> RankingResponse:
    started_at = time.perf_counter()
    cache_key = build_cache_key()

    try:
        cached_payload = validate_ranking_payload(miniredis_client.get(cache_key))
    except RuntimeError as exc:
        metrics_store.record_ranking_cache(duration_ms=(time.perf_counter() - started_at) * 1000, success=False)
        raise HTTPException(status_code=502, detail=f"cache read failed: {exc}") from exc

    if cached_payload is not None:
        logger.info("cache hit key=%s", cache_key)
        metrics_store.record_ranking_cache(
            duration_ms=(time.perf_counter() - started_at) * 1000,
            success=True,
            cache_status="hit",
        )
        return RankingResponse(
            key=cache_key,
            ranking=cached_payload,
            source="cache",
            cache_status="hit",
            cache_ttl_seconds=CACHE_TTL_SECONDS,
        )

    logger.info("cache miss key=%s", cache_key)

    with ranking_cache_lock:
        try:
            second_check_payload = validate_ranking_payload(miniredis_client.get(cache_key))
        except RuntimeError as exc:
            metrics_store.record_ranking_cache(
                duration_ms=(time.perf_counter() - started_at) * 1000,
                success=False,
                cache_status="miss",
            )
            raise HTTPException(status_code=502, detail=f"cache read failed: {exc}") from exc

        if second_check_payload is not None:
            logger.info("cache hit after wait key=%s", cache_key)
            metrics_store.record_ranking_cache(
                duration_ms=(time.perf_counter() - started_at) * 1000,
                success=True,
                cache_status="hit",
            )
            return RankingResponse(
                key=cache_key,
                ranking=second_check_payload,
                source="cache",
                cache_status="hit",
                cache_ttl_seconds=CACHE_TTL_SECONDS,
            )

        ranking, delay_ms = mongo_gateway.compute_ranking(limit=10)
        ranking_payload = RankingPayload.model_validate(ranking)

        try:
            miniredis_client.set(
                cache_key,
                ranking_payload.model_dump(mode="json"),
                ttl_seconds=CACHE_TTL_SECONDS,
            )
        except RuntimeError as exc:
            metrics_store.record_ranking_cache(
                duration_ms=(time.perf_counter() - started_at) * 1000,
                success=False,
                cache_status="miss",
            )
            logger.warning("cache set failed key=%s", cache_key, exc_info=True)
            raise HTTPException(status_code=502, detail=f"cache write failed: {exc}") from exc

    metrics_store.record_ranking_cache(
        duration_ms=(time.perf_counter() - started_at) * 1000,
        success=True,
        cache_status="miss",
    )
    return RankingResponse(
        key=cache_key,
        ranking=ranking_payload,
        source="db",
        cache_status="miss",
        cache_ttl_seconds=CACHE_TTL_SECONDS,
        db_delay_ms=delay_ms,
    )


@app.post("/demo-store", response_model=CachePlaygroundResponse)
def save_demo_store_item(request: CachePlaygroundRequest) -> CachePlaygroundResponse:
    try:
        miniredis_client.set(request.key, request.value, ttl_seconds=request.ttl_seconds)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"cache write failed: {exc}") from exc

    logger.info("manual cache set key=%s ttl_seconds=%s", request.key, request.ttl_seconds)
    return CachePlaygroundResponse(
        success=True,
        operation="set",
        key=request.key,
        exists=True,
        value=request.value,
        ttl_seconds=request.ttl_seconds,
        message="saved",
    )


@app.get("/demo-store", response_model=CachePlaygroundResponse)
def read_demo_store_item(key: str = Query(..., min_length=1)) -> CachePlaygroundResponse:
    try:
        exists = miniredis_client.exists(key)
        value = miniredis_client.get(key) if exists else None
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"cache read failed: {exc}") from exc

    logger.info("manual cache get key=%s exists=%s", key, exists)
    return CachePlaygroundResponse(
        success=exists,
        operation="get",
        key=key,
        exists=exists,
        value=value,
        ttl_seconds=None,
        message="found" if exists else "not found",
    )


@app.delete("/demo-store", response_model=CachePlaygroundResponse)
def delete_demo_store_item(key: str = Query(..., min_length=1)) -> CachePlaygroundResponse:
    try:
        deleted = miniredis_client.delete(key)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"cache delete failed: {exc}") from exc

    logger.info("manual cache delete key=%s deleted=%s", key, deleted)
    return CachePlaygroundResponse(
        success=deleted,
        operation="delete",
        key=key,
        deleted=deleted,
        message="deleted" if deleted else "not found",
    )
