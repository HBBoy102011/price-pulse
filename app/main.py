"""PricePulse — price tracker with parsers, dashboard and Telegram alerts."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import checks, dashboard, demo, products
from app.bot.runner import start_background_bot
from app.config import BASE_DIR, settings
from app.database import init_db
from app.logging_config import configure_logging
from app.scheduler import start_scheduler, stop_scheduler

WEB_DIR = BASE_DIR / "web"
logger = logging.getLogger(__name__)
configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.auto_create_tables:
        init_db()
    start_scheduler()

    bot_task: asyncio.Task | None = None
    if settings.telegram_bot_polling and settings.telegram_bot_token:
        bot_task = asyncio.create_task(start_background_bot(), name="telegram-bot")
        logger.info("Telegram bot polling started in the background")

    try:
        yield
    finally:
        if bot_task is not None:
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                try:
                    await bot_task
                except Exception:
                    logger.exception("Telegram bot task stopped with an error")
        stop_scheduler()


app = FastAPI(
    title="PricePulse API",
    version="1.0.0",
    description=(
        "Трекер цен: парсеры магазинов, история цен, графики, планировщик "
        "и Telegram-уведомления. Учебный проект для портфолио."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)
app.include_router(checks.router)
app.include_router(dashboard.router)
app.include_router(demo.router)

if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return RedirectResponse("/docs")


@app.get("/demo", include_in_schema=False)
def demo_redirect() -> RedirectResponse:
    return RedirectResponse("/demo/shop")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icon = WEB_DIR / "static" / "img" / "favicon.svg"
    if icon.exists():
        return FileResponse(icon, media_type="image/svg+xml")
    return RedirectResponse("/static/img/favicon.svg")
