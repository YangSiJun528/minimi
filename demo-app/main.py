import os

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    service: str
    status: str
    mongodb: str
    miniredis: str


class MongoGateway:
    def __init__(self, uri: str) -> None:
        pass

    def ping(self) -> str:
        pass


class MiniRedisClient:
    def __init__(self, base_url: str) -> None:
        pass

    def health(self) -> str:
        pass

    def set(self, key: str, value: object, ttl_seconds: int | None = None) -> None:
        pass

    def get(self, key: str) -> object | None:
        pass

    def delete(self, key: str) -> bool:
        pass

    def expire(self, key: str, ttl_seconds: int) -> bool:
        pass

    def ttl(self, key: str) -> int | None:
        pass

    def exists(self, key: str) -> bool:
        pass

    def cleanup_expired(self) -> int:
        pass


app = FastAPI(title="Demo App")
mongo_gateway = MongoGateway(os.getenv("MONGODB_URI", "mongodb://localhost:27017/demoapp"))
miniredis_client = MiniRedisClient(os.getenv("MINIREDIS_BASE_URL", "http://localhost:8000"))


@app.get("/health", response_model=HealthResponse)
async def healthcheck() -> HealthResponse:
    pass
