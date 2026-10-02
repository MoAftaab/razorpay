import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .errors import InvalidUpstreamContent, MalformedUpstreamResponse


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _absolute_http_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value
    return None


def parse_search_page(html: str) -> list[dict[str, str | None]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, str | None]] = []

    for card in soup.select("a.package-header"):
        href = _absolute_http_url(card.get("href"))
        name = _clean(card.select_one(".package-name").get_text(" ", strip=True) if card.select_one(".package-name") else None)
        if not href or not name:
            continue

        item_id = urlparse(href).path.rstrip("/").split("/")[-1]
        if not item_id:
            continue

        summary_node = card.select_one(".package-summary")
        license_node = card.select_one(".package-license")
        results.append(
            {
                "item_id": item_id,
                "name": name,
                "summary": _clean(summary_node.get_text(" ", strip=True) if summary_node else None),
                "license": _clean(license_node.get_text(" ", strip=True) if license_node else None),
                "url": href,
            }
        )

    if not results and not soup.select_one("form"):
        raise MalformedUpstreamResponse("search page structure is missing")

    return results


def _link_value(soup: BeautifulSoup, element_id: str) -> str | None:
    node = soup.select_one(f"li.package-link#{element_id}")
    if not node:
        return None
    link = node.select_one("a")
    return _clean(link.get_text(" ", strip=True) if link else node.get_text(" ", strip=True).replace("Author:", "").replace("License:", ""))


def parse_item_page(html: str, item_id: str, page_url: str) -> dict[str, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".package-name")
    if not name_node:
        raise MalformedUpstreamResponse("package name is missing")

    name = _clean(name_node.get_text(" ", strip=True))
    if not name:
        raise MalformedUpstreamResponse("package name is empty")

    summary_node = soup.select_one(".package-summary")
    description_node = soup.select_one(".package-description")
    latest_node = soup.select_one(".package-version#latest .package-version-header")
    latest_version = None
    if latest_node:
        match = re.search(r"\bVersion\s+(.+?)(?:\s+\(|$)", latest_node.get_text(" ", strip=True))
        latest_version = _clean(match.group(1) if match else None)

    source_url = None
    if latest_node:
        source_node = soup.select_one(".package-version#latest .package-version-source a")
        source_url = _absolute_http_url(source_node.get("href") if source_node else None)

    return {
        "item_id": item_id,
        "name": name,
        "summary": _clean(summary_node.get_text(" ", strip=True) if summary_node else None),
        "description": _clean(description_node.get_text(" ", strip=True) if description_node else None),
        "author": _link_value(soup, "author"),
        "license": _link_value(soup, "license"),
        "latest_version": latest_version,
        "source_url": source_url,
        "url": page_url,
    }
