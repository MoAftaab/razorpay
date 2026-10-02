import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.upstream import FDroidClient


SEARCH_HTML = """
<html><body>
  <form class="search-form"></form>
  <a class="package-header" href="https://f-droid.org/en/packages/com.example.notes">
    <h4 class="package-name">Example Notes</h4>
    <div class="package-desc"><span class="package-summary">A private notes app</span><span class="package-license">MIT</span></div>
  </a>
</body></html>
"""

ITEM_HTML = """
<html><body>
  <h3 class="package-name">Example Notes</h3>
  <div class="package-summary">A private notes app</div>
  <div class="package-description">Write and organize notes.<br>Works offline.</div>
  <li class="package-link" id="author">Author: <a href="https://example.com">Example Org</a></li>
  <li class="package-link" id="license">License: <a href="https://spdx.org/licenses/MIT.html">MIT</a></li>
  <li class="package-version" id="latest">
    <div class="package-version-header"><b>Version 1.2.3</b> (123)</div>
    <p class="package-version-source"><a href="https://f-droid.org/repo/example.tar.gz">source</a></p>
  </li>
</body></html>
"""


def make_client(handler) -> FDroidClient:
    transport = httpx.MockTransport(handler)
    return FDroidClient(Settings(), transport=transport)


def client_for(handler) -> TestClient:
    return TestClient(create_app(make_client(handler)))


def test_health_endpoint() -> None:
    with client_for(lambda request: httpx.Response(200, text="unused")) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_successful_search_and_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "search.f-droid.org"
        assert request.url.params["q"] == "notes"
        return httpx.Response(200, text=SEARCH_HTML)

    with client_for(handler) as client:
        response = client.get("/search?query=notes")
    assert response.status_code == 200
    assert response.json() == {
        "query": "notes",
        "items": [{
            "item_id": "com.example.notes",
            "name": "Example Notes",
            "summary": "A private notes app",
            "license": "MIT",
            "url": "https://f-droid.org/en/packages/com.example.notes",
        }],
    }


def test_successful_item_lookup() -> None:
    with client_for(lambda request: httpx.Response(200, text=ITEM_HTML)) as client:
        response = client.get("/items/com.example.notes")
    assert response.status_code == 200
    body = response.json()
    assert body["item_id"] == "com.example.notes"
    assert body["latest_version"] == "1.2.3"
    assert body["author"] == "Example Org"
    assert body["description"] == "Write and organize notes. Works offline."


@pytest.mark.parametrize("url", ["/search?query=", "/search?query=%20%20", "/items/not%20valid"])
def test_empty_or_invalid_query_returns_validation_error(url: str) -> None:
    with client_for(lambda request: httpx.Response(200, text=SEARCH_HTML)) as client:
        response = client.get(url)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


def test_nonexistent_item() -> None:
    with client_for(lambda request: httpx.Response(404, text="not found")) as client:
        response = client.get("/items/com.example.missing")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "item_not_found"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_upstream_4xx_and_5xx_are_hidden_behind_502(status: int) -> None:
    with client_for(lambda request: httpx.Response(status, text="upstream error")) as client:
        response = client.get("/search?query=notes")
    assert response.status_code == 502
    assert response.json()["detail"] == {"code": "upstream_error", "message": "The public catalog returned an error."}


def test_upstream_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with client_for(handler) as client:
        response = client.get("/search?query=notes")
    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "upstream_timeout"


def test_upstream_network_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with client_for(handler) as client:
        response = client.get("/search?query=notes")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "upstream_unavailable"


def test_malformed_upstream_response() -> None:
    with client_for(lambda request: httpx.Response(200, text="<html><body>no package here</body></html>")) as client:
        response = client.get("/items/com.example.notes")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "upstream_malformed"


def test_malformed_search_response() -> None:
    with client_for(lambda request: httpx.Response(200, text="<html><body>not a search page</body></html>")) as client:
        response = client.get("/search?query=notes")
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "upstream_malformed"
