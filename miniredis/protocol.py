from __future__ import annotations

from typing import TypeAliasType

from pydantic import BaseModel, Field

JSONValue = TypeAliasType(
    "JSONValue",
    dict[str, "JSONValue"] | list["JSONValue"] | str | int | float | bool | None,
)


class BaseResponse(BaseModel):
    success: bool
    message: str | None = None


class SetRequest(BaseModel):
    key: str = Field(..., min_length=1)
    value: JSONValue
    ttl_seconds: int | None = Field(default=None, ge=0)


class KeyRequest(BaseModel):
    key: str = Field(..., min_length=1)


class ExpireRequest(BaseModel):
    key: str = Field(..., min_length=1)
    ttl_seconds: int = Field(..., ge=0)


class GetResponse(BaseResponse):
    key: str
    value: JSONValue = None
    found: bool


class TTLResponse(BaseResponse):
    key: str
    ttl_seconds: int | None = None
    found: bool


class ExistsResponse(BaseResponse):
    key: str
    exists: bool


class CleanupExpiredResponse(BaseResponse):
    removed_count: int
