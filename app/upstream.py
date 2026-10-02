import logging
from urllib.parse import quote

import httpx

from .config import Settings
from .errors import (
    MalformedUpstreamResponse,
    UpstreamHttpError,
    UpstreamNotFound,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from .parser import parse_item_page, parse_search_page

logger = logging.getLogger(__name__)


class FDroidClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.timeout_seconds),
            headers={"User-Agent": settings.user_agent, "Accept": "text/html"},
            transport=transport,
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, url: str) -> str:
        try:
            response = await self._http.get(url)
        except httpx.TimeoutException as exc:
            logger.warning("F-Droid request timed out", extra={"url": url})
            raise UpstreamTimeout from exc
        except httpx.RequestError as exc:
            logger.warning("F-Droid request failed: %s", exc, extra={"url": url})
            raise UpstreamUnavailable from exc

        if response.status_code == 404:
            raise UpstreamNotFound
        if response.status_code >= 400:
            raise UpstreamHttpError(response.status_code)
        if not response.text.strip():
            raise MalformedUpstreamResponse("empty upstream response")
        return response.text

    async def search(self, query: str) -> list[dict[str, str | None]]:
        url = f"{self.settings.search_url}?lang=en&q={quote(query)}"
        try:
            html = await self._get(url)
        except UpstreamNotFound as exc:
            raise UpstreamHttpError(404) from exc
        try:
            return parse_search_page(html)
        except (ValueError, TypeError) as exc:
            raise MalformedUpstreamResponse("could not parse search response") from exc

    async def get_item(self, item_id: str) -> dict[str, str | None]:
        url = f"{self.settings.item_url}/{quote(item_id, safe='')}/"
        html = await self._get(url)
        try:
            return parse_item_page(html, item_id, url)
        except (ValueError, TypeError) as exc:
            raise MalformedUpstreamResponse("could not parse item response") from exc
