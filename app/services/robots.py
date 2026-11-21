"""robots.txt checks with a small in-process cache."""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.config import settings
from app.parsers.base import USER_AGENT

logger = logging.getLogger(__name__)

_CACHE_TTL = 6 * 60 * 60
_cache: dict[str, tuple[float, RobotFileParser | None]] = {}
_AGENT = "PricePulseBot"


async def robots_allowed(url: str) -> tuple[bool, str | None]:
    """Return ``(allowed, reason)`` for the given URL.

    If robots.txt cannot be fetched we allow the request but log a warning:
    blocking the whole tracker because of a network hiccup would be worse for
    the demo. Real shops are still rate-limited by the scheduler.
    """
    if not settings.robots_check_enabled:
        return True, None

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return True, None

    origin = f"{parsed.scheme}://{parsed.netloc}"
    cached = _cache.get(origin)
    if cached and time.time() - cached[0] < _CACHE_TTL:
        parser = cached[1]
        if parser is None:
            return True, None
        allowed = parser.can_fetch(_AGENT, url)
        return allowed, None if allowed else "robots.txt запрещает обход этой страницы"

    robots_url = f"{origin}/robots.txt"
    parser: RobotFileParser | None = None
    try:
        async with httpx.AsyncClient(
            timeout=min(settings.request_timeout_seconds, 10),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(robots_url)
        if response.status_code < 400:
            parser = RobotFileParser()
            parser.parse(response.text.splitlines())
        else:
            logger.info(
                "robots.txt %s -> HTTP %s, assuming allowed", robots_url, response.status_code
            )
    except httpx.HTTPError as exc:
        logger.warning("robots.txt %s unavailable (%s), assuming allowed", robots_url, exc)

    _cache[origin] = (time.time(), parser)
    if parser is None:
        return True, None
    allowed = parser.can_fetch(_AGENT, url)
    return allowed, None if allowed else "robots.txt запрещает обход этой страницы"


def clear_cache() -> None:
    _cache.clear()
