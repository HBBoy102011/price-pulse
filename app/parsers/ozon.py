"""Ozon parser (best effort).

Ozon renders prices into JSON-LD, which is the most stable part of the page.
The shop actively protects its storefront, so the parser fails gracefully and
the service marks the product as problematic instead of crashing.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from app.parsers.base import (
    BaseParser,
    ParsedProduct,
    ParserError,
    clean_text,
    host_of,
    json_ld_products,
    parse_price,
)

PRICE_IN_SCRIPT_RE = re.compile(r'"price"\s*:\s*"?([\d]+(?:[.,]\d{1,2})?)"?')
TRAILING_ID_RE = re.compile(r"-(\d+)/?$")


class OzonParser(BaseParser):
    shop_id = "ozon"
    shop_name = "Ozon"
    sample_url = "https://www.ozon.ru/product/1234567890/"
    note = "JSON-LD + резервный разбор HTML (Ozon может ограничивать доступ)"

    def can_handle(self, url: str) -> bool:
        host = host_of(url)
        return host.endswith("ozon.ru")

    async def parse(self, url: str) -> ParsedProduct:
        html = await self.fetch_text(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Sec-Fetch-Mode": "navigate",
            },
        )
        return self.parse_html(html, url)

    def parse_html(self, html: str, url: str) -> ParsedProduct:
        soup = BeautifulSoup(html, "html.parser")

        for item in json_ld_products(soup):
            title = clean_text(item.get("name"))
            offers = item.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            raw_price = offers.get("price") or offers.get("lowPrice")
            if not title or raw_price is None:
                continue
            availability = str(offers.get("availability") or "").lower()
            image = item.get("image")
            if isinstance(image, list):
                image = image[0] if image else None
            return ParsedProduct(
                title=title,
                price=parse_price(raw_price),
                currency=str(offers.get("priceCurrency") or "RUB").upper(),
                in_stock="outofstock" not in availability,
                image_url=image,
                external_id=self._external_id(url),
                shop=self.shop_id,
            )

        # Fallback: og:title + the first sensible price in embedded JSON.
        og_title = soup.select_one('meta[property="og:title"]')
        title = clean_text(og_title.get("content") if og_title else None)
        if not title:
            h1 = soup.select_one("h1")
            title = clean_text(h1.get_text() if h1 else None)

        match = PRICE_IN_SCRIPT_RE.search(html)
        if not title or not match:
            raise ParserError("Ozon не отдал цену в разметке — вероятно, сработала антибот-защита")

        og_image = soup.select_one('meta[property="og:image"]')
        return ParsedProduct(
            title=title,
            price=parse_price(match.group(1)),
            currency="RUB",
            in_stock=True,
            image_url=og_image.get("content") if og_image else None,
            external_id=self._external_id(url),
            shop=self.shop_id,
        )

    @staticmethod
    def _external_id(url: str) -> str | None:
        match = TRAILING_ID_RE.search(url.rstrip("/") + "/")
        return match.group(1) if match else None
