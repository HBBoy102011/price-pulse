"""Standalone bot entry point: ``python -m app.bot``."""

from __future__ import annotations

import asyncio

from app.bot.runner import run_bot
from app.logging_config import configure_logging


def main() -> None:
    configure_logging()
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nBot stopped.")


if __name__ == "__main__":
    main()
