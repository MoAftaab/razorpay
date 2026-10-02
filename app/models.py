from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    errors: list[dict[str, object]] | None = None


class ErrorResponse(BaseModel):
    detail: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"]


class AppSummary(BaseModel):
    item_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    summary: str | None = None
    license: str | None = None
    url: AnyHttpUrl


class SearchResponse(BaseModel):
    query: str = Field(min_length=1)
    items: list[AppSummary]


class AppDetail(BaseModel):
    item_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    summary: str | None = None
    description: str | None = None
    author: str | None = None
    license: str | None = None
    latest_version: str | None = None
    source_url: AnyHttpUrl | None = None
    url: AnyHttpUrl

