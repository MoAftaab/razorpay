from contextlib import asynccontextmanager
import logging
import re
from typing import AsyncIterator

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings
from .errors import (
    MalformedUpstreamResponse,
    UpstreamHttpError,
    UpstreamNotFound,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from .models import AppDetail, ErrorResponse, HealthResponse, SearchResponse
from .upstream import FDroidClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ITEM_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def _error(code: str, message: str, status_code: int, errors: list[dict[str, object]] | None = None) -> JSONResponse:
    body = {"detail": {"code": code, "message": message}}
    if errors is not None:
        body["detail"]["errors"] = errors
    return JSONResponse(status_code=status_code, content=body)


def create_app(client: FDroidClient | None = None) -> FastAPI:
    settings = Settings.from_env()
    upstream = client or FDroidClient(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await upstream.close()

    api = FastAPI(
        title="F-Droid Catalog Adapter",
        version="1.0.0",
        description="A stable API over F-Droid's public HTML catalog pages.",
        lifespan=lifespan,
    )

    @api.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"location": list(error.get("loc", ())), "message": error.get("msg", "Invalid value")} for error in exc.errors()]
        return _error("validation_error", "The request parameters are invalid.", 422, errors)

    @api.exception_handler(UpstreamNotFound)
    async def not_found_handler(_: Request, __: UpstreamNotFound) -> JSONResponse:
        return _error("item_not_found", "The requested item was not found in F-Droid's public catalog.", 404)

    @api.exception_handler(UpstreamTimeout)
    async def timeout_handler(_: Request, __: UpstreamTimeout) -> JSONResponse:
        return _error("upstream_timeout", "The public catalog did not respond in time.", 504)

    @api.exception_handler(UpstreamHttpError)
    async def upstream_http_handler(_: Request, __: UpstreamHttpError) -> JSONResponse:
        return _error("upstream_error", "The public catalog returned an error.", 502)

    @api.exception_handler(UpstreamUnavailable)
    async def unavailable_handler(_: Request, __: UpstreamUnavailable) -> JSONResponse:
        return _error("upstream_unavailable", "The public catalog is temporarily unavailable.", 502)

    @api.exception_handler(MalformedUpstreamResponse)
    async def malformed_handler(_: Request, __: MalformedUpstreamResponse) -> JSONResponse:
        return _error("upstream_malformed", "The public catalog returned an unexpected response.", 502)

    @api.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/search", response_model=SearchResponse, responses={422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}}, tags=["catalog"])
    async def search(query: str = Query(min_length=1, max_length=100)) -> SearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            return _error("validation_error", "query must not be blank.", 422)  # type: ignore[return-value]
        items = await upstream.search(normalized_query)
        return SearchResponse(query=normalized_query, items=items)

    @api.get("/items/{item_id}", response_model=AppDetail, responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}}, tags=["catalog"])
    async def item(item_id: str = Path(min_length=1, max_length=200)) -> AppDetail:
        if not ITEM_ID_PATTERN.fullmatch(item_id):
            return _error("validation_error", "item_id contains unsupported characters.", 422)  # type: ignore[return-value]
        return AppDetail(**(await upstream.get_item(item_id)))

    return api


app = create_app()

