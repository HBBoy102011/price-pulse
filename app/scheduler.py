"""APScheduler wiring: periodic price checks."""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import settings
from app.database import SessionLocal
from app.services.price_service import check_all
from app.services.stats import as_utc

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)
JOB_ID = "price-check"


async def run_scheduled_check() -> None:
    logger.info("Scheduled price check started")
    db = SessionLocal()
    try:
        summary = await check_all(db, force=False)
        logger.info("Scheduled price check done: %s", summary.model_dump(exclude={"results"}))
    except Exception:
        logger.exception("Scheduled price check crashed")
    finally:
        db.close()


def start_scheduler() -> None:
    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled by configuration")
        return
    if scheduler.running:
        return
    scheduler.add_job(
        run_scheduled_check,
        trigger=IntervalTrigger(hours=settings.check_interval_hours),
        id=JOB_ID,
        name="Проверка цен",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
        jitter=120,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: every %s h (timezone %s)",
        settings.check_interval_hours,
        settings.scheduler_timezone,
    )


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def next_run_time() -> datetime | None:
    if not scheduler.running:
        return None
    job = scheduler.get_job(JOB_ID)
    return as_utc(job.next_run_time) if job and job.next_run_time else None
