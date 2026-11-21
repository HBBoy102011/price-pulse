from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.parsers.base import ParserError, parse_price
from app.parsers.demo import DemoShopParser
from app.parsers.ozon import OzonParser
from app.parsers.registry import UnknownShopError, get_parser, supported_shops
from app.parsers.wildberries import WildberriesParser

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12 990 ₽", 12990.0),
        ("12 990,50 ₽", 12990.5),
        ("1 299,00 ₽", 1299.0),
        ("$1,299.00", 1299.0),
        ("1.299,00 €", 1299.0),
        (12990, 12990.0),
        (12990.5, 12990.5),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_parse_price_rejects_garbage():
    with pytest.raises(ParserError):
        parse_price("нет цены")


def test_demo_parser_fixture():
    html = (FIXTURES / "demo_product.html").read_text(encoding="utf-8")
    parsed = DemoShopParser().parse_html(
        html, "https://pricepulse.local/demo/shop/aurora-headphones"
    )
    assert parsed.title == "Aurora Studio ANC"
    assert parsed.price == 23409.0
    assert parsed.currency == "RUB"
    assert parsed.in_stock is True
    assert parsed.external_id == "aurora-headphones"
    assert parsed.image_url.endswith("aurora-headphones.svg")


def test_demo_parser_detection():
    parser = DemoShopParser()
    assert parser.can_handle("http://localhost:8000/demo/shop/nova-watch")
    assert not parser.can_handle("https://www.wildberries.ru/catalog/1/detail.aspx")


def test_wildberries_payload_fixture():
    payload = json.loads((FIXTURES / "wildberries_card.json").read_text(encoding="utf-8"))
    parser = WildberriesParser()
    parsed = parser.parse_payload(
        payload, "https://www.wildberries.ru/catalog/182203524/detail.aspx"
    )
    assert parsed.title == "Кроссовки Drift Runner V3"
    assert parsed.price == 8499.0
    assert parsed.external_id == "182203524"
    assert parsed.in_stock is True
    assert parsed.image_url and "wbbasket.ru" in parsed.image_url


def test_wildberries_detection_and_nm():
    parser = WildberriesParser()
    url = "https://www.wildberries.ru/catalog/182203524/detail.aspx?targetUrl=GP"
    assert parser.can_handle(url)
    assert parser.extract_nm(url) == "182203524"
    assert not parser.can_handle("https://www.ozon.ru/product/123/")


def test_ozon_json_ld_fixture():
    html = (FIXTURES / "ozon_product.html").read_text(encoding="utf-8")
    parsed = OzonParser().parse_html(html, "https://www.ozon.ru/product/brew-master-123456/")
    assert parsed.title == "Кофемашина Brew Master Pro"
    assert parsed.price == 54990.0
    assert parsed.currency == "RUB"
    assert parsed.in_stock is True
    assert parsed.external_id == "123456"


def test_registry():
    assert isinstance(
        get_parser("https://www.wildberries.ru/catalog/1/detail.aspx"), WildberriesParser
    )
    assert isinstance(get_parser("https://www.ozon.ru/product/x-1/"), OzonParser)
    assert isinstance(get_parser("http://localhost/demo/shop/a"), DemoShopParser)
    with pytest.raises(UnknownShopError):
        get_parser("https://example.com/product/1")
    assert len(supported_shops()) == 3
