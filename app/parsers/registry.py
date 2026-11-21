"""Parser registry: maps a URL to the right shop module."""

from __future__ import annotations

from app.parsers.base import BaseParser, ParsedProduct, ParserError
from app.parsers.demo import DemoShopParser
from app.parsers.ozon import OzonParser
from app.parsers.wildberries import WildberriesParser

PARSERS: list[BaseParser] = [
    DemoShopParser(),
    WildberriesParser(),
    OzonParser(),
]

SHOP_NAMES = {parser.shop_id: parser.shop_name for parser in PARSERS}


class UnknownShopError(ParserError):
    pass


def get_parser(url: str) -> BaseParser:
    for parser in PARSERS:
        if parser.can_handle(url):
            return parser
    raise UnknownShopError(
        "Этот магазин пока не поддерживается. Доступны: "
        + ", ".join(parser.shop_name for parser in PARSERS)
    )


async def parse_product(url: str) -> ParsedProduct:
    parser = get_parser(url)
    parsed = await parser.parse(url)
    parsed.shop = parser.shop_id
    return parsed


def supported_shops() -> list[dict[str, str | None]]:
    return [
        {
            "id": parser.shop_id,
            "name": parser.shop_name,
            "sample_url": parser.sample_url,
            "note": parser.note,
        }
        for parser in PARSERS
    ]
