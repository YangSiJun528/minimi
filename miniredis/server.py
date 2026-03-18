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


@app.get("/health", response_model=BaseResponse)
async def healthcheck() -> BaseResponse:
    pass


@app.post("/set", response_model=BaseResponse)
async def set_value(request: SetRequest) -> BaseResponse:
    pass


@app.post("/get", response_model=GetResponse)
async def get_value(request: KeyRequest) -> GetResponse:
    pass


@app.post("/delete", response_model=BaseResponse)
async def delete_value(request: KeyRequest) -> BaseResponse:
    pass


@app.post("/exists", response_model=ExistsResponse)
async def exists_value(request: KeyRequest) -> ExistsResponse:
    pass
