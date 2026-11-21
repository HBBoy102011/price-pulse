"""Parser for the built-in demo store.

The demo store lives inside this FastAPI app (``/demo/shop``) and behaves like
a real shop: prices drift over time, so the scheduler always has something to
record. It is also the most reliable shop for a portfolio demo and for tests.
"""

from __future__ import annotations

from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.parsers.base import BaseParser, ParsedProduct, ParserError, clean_text, parse_price


class DemoShopParser(BaseParser):
    shop_id = "demo"
    shop_name = "Demo Store"
    sample_url = "/demo/shop/aurora-headphones"
    note = "Встроенный демо-магазин: работает без внешней сети"

    def can_handle(self, url: str) -> bool:
        path = urlparse(url).path
        return path.startswith("/demo/shop/") and path.count("/") >= 3

    async def parse(self, url: str) -> ParsedProduct:
        html = await self.fetch_text(url)
        return self.parse_html(html, url)

    def parse_html(self, html: str, url: str) -> ParsedProduct:
        soup = BeautifulSoup(html, "html.parser")

        title_el = soup.select_one("[data-product-title]")
        price_el = soup.select_one("[data-product-price]")
        if price_el is None:
            raise ParserError("На странице не найден блок с ценой")

        title = clean_text(title_el.get_text() if title_el else None)
        if not title:
            og_title = soup.select_one('meta[property="og:title"]')
            title = clean_text(og_title.get("content") if og_title else None)
        if not title:
            raise ParserError("Не удалось определить название товара")

        price = parse_price(price_el.get_text())
        image_el = soup.select_one("[data-product-image]")
        image_url = None
        if image_el is not None:
            image_url = image_el.get("src") or image_el.get("data-src")
        if not image_url:
            og_image = soup.select_one('meta[property="og:image"]')
            image_url = og_image.get("content") if og_image else None

        stock_el = soup.select_one("[data-product-stock]")
        in_stock = True
        if stock_el is not None:
            in_stock = stock_el.get("data-in-stock") != "false"

        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        currency = "RUB"
        currency_el = soup.select_one("[data-product-currency]")
        if currency_el is not None and currency_el.get_text(strip=True):
            currency = currency_el.get_text(strip=True).upper()

        return ParsedProduct(
            title=title,
            price=price,
            currency=currency,
            in_stock=in_stock,
            image_url=image_url,
            external_id=slug,
            shop=self.shop_id,
        )
