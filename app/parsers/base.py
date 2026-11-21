"""Shared parser primitives: HTTP fetching, price normalisation, base class."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

USER_AGENT = (
    "PricePulseBot/1.0 (+https://github.com/HBBoy102011/price-pulse; "
    "educational price tracker; contact: portfolio project)"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}


class ParserError(RuntimeError):
    """Raised when a page cannot be parsed into a product."""


@dataclass(slots=True)
class ParsedProduct:
    title: str
    price: float
    currency: str = "RUB"
    in_stock: bool = True
    image_url: str | None = None
    external_id: str | None = None
    shop: str = ""


class BaseParser(ABC):
    """Every shop parser implements the same tiny interface."""

    shop_id: str
    shop_name: str
    sample_url: str | None = None
    note: str | None = None

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Return True when this parser knows how to work with the URL."""

    @abstractmethod
    async def parse(self, url: str) -> ParsedProduct:
        """Fetch the page/API and return a normalised product."""

    async def fetch_text(self, url: str, *, headers: dict[str, str] | None = None) -> str:
        merged = {**DEFAULT_HEADERS, **(headers or {})}
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers=merged,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text

    async def fetch_json(self, url: str, *, headers: dict[str, str] | None = None) -> Any:
        merged = {**DEFAULT_HEADERS, "Accept": "application/json", **(headers or {})}
        async with httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
            headers=merged,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()


_PRICE_CLEAN_RE = re.compile(r"[^\d,.\-]")


def parse_price(raw: str | float | int | None) -> float:
    """Parse ``12 990,50 ₽`` / ``$1,299.00`` / ``12990`` into a float."""
    if raw is None:
        raise ParserError("Цена не найдена")
    if isinstance(raw, int | float):
        return round(float(raw), 2)

    text = _PRICE_CLEAN_RE.sub("", str(raw)).strip()
    if not text:
        raise ParserError("Цена не найдена")

    if "," in text and "." in text:
        # 1,299.00 -> 1299.00 ; 1.299,00 -> 1299.00
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        value = float(text)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ParserError(f"Не удалось разобрать цену: {raw!r}") from exc
    if value <= 0:
        raise ParserError(f"Некорректная цена: {raw!r}")
    return round(value, 2)


def json_ld_products(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Return every schema.org Product object found in JSON-LD blocks."""
    found: list[dict[str, Any]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        payload = script.string or script.get_text()
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                candidates.extend(graph)
            item_type = item.get("@type")
            types = item_type if isinstance(item_type, list) else [item_type]
            if any(str(t).lower() == "product" for t in types):
                found.append(item)
    return found


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def path_of(url: str) -> str:
    return urlparse(url).path.rstrip("/") or "/"
