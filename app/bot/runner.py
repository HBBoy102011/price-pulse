"""Long-polling loop for the Telegram bot.

The same loop powers both deployment styles:

* ``python -m app.bot`` — a dedicated bot process;
* ``TELEGRAM_BOT_POLLING=true`` — a background task inside the FastAPI app.

Only one poller may run per bot token, otherwise Telegram splits updates
between them. Keep the web app at one worker when polling is enabled.
"""

from __future__ import annotations

import asyncio
import logging

from app.bot.client import TelegramAPI
from app.bot.handlers import BotHandlers
from app.config import settings

logger = logging.getLogger(__name__)


async def poll_forever(
    api: TelegramAPI,
    handlers: BotHandlers,
    *,
    stop: asyncio.Event | None = None,
) -> None:
    me = await api.get_me()
    username = me.get("username") or "unknown"
    logger.info("Telegram bot @%s is polling for updates", username)

    offset = 0
    while stop is None or not stop.is_set():
        try:
            updates = await api.get_updates(offset=offset, timeout=25)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Telegram getUpdates failed: %s", exc)
            await asyncio.sleep(3)
            continue

        for update in updates:
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            try:
                await handlers.handle_update(update)
            except Exception:
                logger.exception("Failed to handle Telegram update %s", update.get("update_id"))


async def run_bot() -> None:
    """Run a standalone poller until the process is interrupted."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    api = TelegramAPI(settings.telegram_bot_token)
    try:
        await poll_forever(api, BotHandlers(api))
    finally:
        await api.close()


async def start_background_bot() -> None:
    """Entry point for the FastAPI lifespan task."""
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_POLLING is enabled but TELEGRAM_BOT_TOKEN is empty")
        return
    await run_bot()
