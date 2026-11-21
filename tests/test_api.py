from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.api import products as products_api
from app.parsers.base import ParsedProduct, ParserError
from app.services import price_service


@pytest.fixture()
def fake_parser(monkeypatch):
    async def fake_parse(_url: str) -> ParsedProduct:
        return ParsedProduct(
            title="Тестовый товар",
            price=1000.0,
            currency="RUB",
            in_stock=True,
            image_url="/static/img/products/echo-speaker.svg",
            external_id="test-1",
            shop="demo",
        )

    async def allowed(_url: str):
        return True, None

    monkeypatch.setattr(price_service, "parse_product", fake_parse)
    monkeypatch.setattr(products_api, "parse_product", fake_parse)
    monkeypatch.setattr(price_service, "get_parser", lambda _url: SimpleNamespace(parse=fake_parse))
    monkeypatch.setattr(price_service, "robots_allowed", allowed)
    return fake_parse


def add_product(client, url="https://example.com/demo/shop/test-1", target=1200):
    return client.post(
        "/api/products",
        json={"url": url, "target_price": target, "target_discount_percent": 10},
    )


def test_add_list_update_delete(client, fake_parser):
    response = add_product(client)
    assert response.status_code == 201, response.text
    product = response.json()
    assert product["title"] == "Тестовый товар"
    assert product["current_price"] == 1000.0
    assert product["below_target"] is True
    assert product["status"] == "active"
    product_id = product["id"]

    listing = client.get("/api/products").json()
    assert len(listing) == 1
    assert listing[0]["id"] == product_id

    patched = client.patch(
        f"/api/products/{product_id}",
        json={"target_price": 900, "status": "paused"},
    )
    assert patched.status_code == 200
    assert patched.json()["target_price"] == 900.0
    assert patched.json()["status"] == "paused"

    filtered = client.get("/api/products?status=paused").json()
    assert len(filtered) == 1

    deleted = client.delete(f"/api/products/{product_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/products/{product_id}").status_code == 404


def test_duplicate_product(client, fake_parser):
    assert add_product(client).status_code == 201
    duplicate = add_product(client)
    assert duplicate.status_code == 409
    assert "уже отслеживается" in duplicate.json()["detail"]


def test_preview(client, fake_parser):
    response = client.post("/api/preview", json={"url": "https://example.com/demo/shop/test-1"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Тестовый товар"
    assert data["price"] == 1000.0
    assert data["shop"] == "demo"


def test_preview_parser_error(client, monkeypatch):
    async def broken(_url: str):
        raise ParserError("Страница недоступна")

    monkeypatch.setattr(products_api, "parse_product", broken)
    response = client.post("/api/preview", json={"url": "https://example.com/x"})
    assert response.status_code == 422
    assert "недоступна" in response.json()["detail"]


def test_history_and_csv(client, fake_parser):
    product_id = add_product(client).json()["id"]
    history = client.get(f"/api/products/{product_id}/history?days=30")
    assert history.status_code == 200
    payload = history.json()
    assert payload["points"][0]["price"] == 1000.0
    assert payload["stats"]["min_price"] == 1000.0
    assert payload["stats"]["change_count"] == 0

    export = client.get(f"/api/products/{product_id}/history.csv")
    assert export.status_code == 200
    assert export.content.startswith(b"\xef\xbb\xbf")
    assert "checked_at" in export.text


def test_manual_check_changes_price(client, fake_parser, monkeypatch):
    product_id = add_product(client).json()["id"]

    async def cheaper(_url: str):
        return ParsedProduct(title="Тестовый товар", price=800.0, shop="demo")

    monkeypatch.setattr(price_service, "get_parser", lambda _url: SimpleNamespace(parse=cheaper))
    response = client.post("/api/check", json={"force": True})
    assert response.status_code == 200
    summary = response.json()
    assert summary["checked"] == 1
    assert summary["changed"] == 1
    assert summary["failed"] == 0

    history = client.get(f"/api/products/{product_id}/history?days=30").json()
    assert len(history["points"]) == 2
    assert history["points"][-1]["price"] == 800.0


def test_summary_and_notifications(client, fake_parser):
    add_product(client)
    summary = client.get("/api/summary").json()
    assert summary["total_products"] == 1
    assert summary["active_products"] == 1
    assert summary["below_target"] == 1
    assert summary["checks_today"] >= 1

    feed = client.get("/api/notifications").json()
    assert len(feed) == 1
    assert feed[0]["kind"] == "target"
    assert feed[0]["status"] == "skipped"

    shops = client.get("/api/shops").json()
    assert {shop["id"] for shop in shops} == {"demo", "wildberries", "ozon"}


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
