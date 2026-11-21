"""Wildberries parser built on the public card JSON endpoint.

No HTML scraping: Wildberries' own storefront uses this JSON API, which is
faster and much more stable than parsing markup.
"""

from __future__ import annotations

import re

from app.parsers.base import BaseParser, ParsedProduct, ParserError, clean_text, host_of

CARD_API = (
    "https://card.wb.ru/cards/v2/detail"
    "?appType=1&curr=rub&dest=-1257786&spp=30&hide_dtype=13&nm={nm}"
)
NM_RE = re.compile(r"/(?:catalog|product)/(\d+)")
VOLUME_RE = re.compile(r"vol(\d+)/part(\d+)/(\d+)/")


class WildberriesParser(BaseParser):
    shop_id = "wildberries"
    shop_name = "Wildberries"
    sample_url = "https://www.wildberries.ru/catalog/182203524/detail.aspx"
    note = "Публичный JSON API карточки товара"

    def can_handle(self, url: str) -> bool:
        host = host_of(url)
        return (host.endswith("wildberries.ru") or host.endswith("wb.ru")) and bool(
            NM_RE.search(url)
        )

    def extract_nm(self, url: str) -> str:
        match = NM_RE.search(url)
        if not match:
            raise ParserError("В ссылке Wildberries не найден артикул (nm)")
        return match.group(1)

    async def parse(self, url: str) -> ParsedProduct:
        nm = self.extract_nm(url)
        payload = await self.fetch_json(CARD_API.format(nm=nm))
        return self.parse_payload(payload, url)

    def parse_payload(self, payload: dict, url: str) -> ParsedProduct:
        products = (payload.get("data") or {}).get("products") or payload.get("products") or []
        if not products:
            raise ParserError("Wildberries не вернул данные о товаре (возможно, товар скрыт)")

        item = products[0]
        nm = int(item.get("id") or self.extract_nm(url))
        name = clean_text(item.get("name"))
        brand = clean_text(item.get("brand"))
        if not name:
            raise ParserError("Wildberries не вернул название товара")
        title = name if not brand or brand.lower() in name.lower() else f"{brand} / {name}"

        price = self._extract_price(item, nm)
        image_url = self._image_url(nm)
        in_stock = int(item.get("totalQuantity") or 0) > 0

        return ParsedProduct(
            title=title,
            price=price,
            currency="RUB",
            in_stock=in_stock,
            image_url=image_url,
            external_id=str(nm),
            shop=self.shop_id,
        )

    @staticmethod
    def _extract_price(item: dict, nm: int) -> float:
        sizes = item.get("sizes") or []
        for size in sizes:
            price_block = size.get("price") or {}
            for key in ("product", "total", "basic"):
                value = price_block.get(key)
                if value:
                    return round(float(value) / 100, 2)

        for key in ("salePriceU", "priceU", "salePrice", "price"):
            value = item.get(key)
            if value:
                value = float(value)
                return round(value / 100 if value > 100_000 else value, 2)

        raise ParserError(f"Не удалось получить цену товара {nm}")

    @staticmethod
    def _image_url(nm: int) -> str | None:
        vol = nm // 100_000
        part = nm // 1_000
        basket = 1
        for threshold, number in (
            (143, 1),
            (287, 2),
            (431, 3),
            (719, 4),
            (1007, 5),
            (1061, 6),
            (1115, 7),
            (1169, 8),
            (1313, 9),
            (1601, 10),
            (1655, 11),
            (1919, 12),
            (2045, 13),
            (2189, 14),
            (2405, 15),
            (2621, 16),
            (2837, 17),
            (3053, 18),
            (3269, 19),
            (3485, 20),
            (3701, 21),
            (3917, 22),
            (4133, 23),
            (4349, 24),
            (4565, 25),
            (4877, 26),
        ):
            if vol <= threshold:
                basket = number
                break
        return f"https://basket-{basket:02d}.wbbasket.ru/vol{vol}/part{part}/{nm}/images/big/1.webp"
