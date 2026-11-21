"""Dashboard summary, notification feed and health check."""

from __future__ import annotations

from datetime import timedelta
from statistics import mean
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.models import (
    PRODUCT_ACTIVE,
    PRODUCT_ERROR,
    PRODUCT_PAUSED,
    Notification,
    PriceHistory,
    Product,
    utcnow,
)
from app.scheduler import next_run_time, scheduler
from app.schemas import DashboardSummary, HealthOut, NotificationOut
from app.services.stats import as_utc, to_float

router = APIRouter(prefix="/api", tags=["dashboard"])
DbSession = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=DashboardSummary)
def summary(db: DbSession) -> DashboardSummary:
    products = list(db.scalars(select(Product)).all())
    now = utcnow()
    since_30d = now - timedelta(days=30)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    history_rows = db.execute(
        select(PriceHistory.product_id, PriceHistory.price).where(
            PriceHistory.checked_at >= since_30d
        )
    ).all()
    prices_by_product: dict[int, list[float]] = {}
    for product_id, price in history_rows:
        prices_by_product.setdefault(product_id, []).append(float(price))

    max_rows = db.execute(
        select(PriceHistory.product_id, func.max(PriceHistory.price)).group_by(
            PriceHistory.product_id
        )
    ).all()
    max_by_product = {product_id: float(price) for product_id, price in max_rows}

    discounts: list[float] = []
    savings = 0.0
    for product in products:
        current = to_float(product.last_price)
        if current is None:
            continue
        prices = prices_by_product.get(product.id, [])
        if prices:
            peak_30d = max(prices)
            if peak_30d > 0 and peak_30d >= current:
                discounts.append((1 - current / peak_30d) * 100)
        peak = max_by_product.get(product.id)
        if peak and peak > current:
            savings += peak - current

    with_target = sum(1 for product in products if product.target_price is not None)
    below_target = sum(
        1
        for product in products
        if product.target_price is not None
        and product.last_price is not None
        and product.last_price <= product.target_price
    )
    checks_today = (
        db.scalar(select(func.count(PriceHistory.id)).where(PriceHistory.checked_at >= midnight))
        or 0
    )
    notifications_count = db.scalar(select(func.count(Notification.id))) or 0

    return DashboardSummary(
        total_products=len(products),
        active_products=sum(1 for product in products if product.status == PRODUCT_ACTIVE),
        paused_products=sum(1 for product in products if product.status == PRODUCT_PAUSED),
        error_products=sum(1 for product in products if product.status == PRODUCT_ERROR),
        below_target=below_target,
        with_target=with_target,
        average_discount=round(mean(discounts), 1) if discounts else None,
        checks_today=checks_today,
        notifications_sent=notifications_count,
        savings_from_peak=round(savings, 2),
        next_check_at=next_run_time(),
        scheduler_running=scheduler.running,
        check_interval_hours=settings.check_interval_hours,
        telegram_configured=settings.telegram_configured,
    )


@router.get("/notifications", response_model=list[NotificationOut])
def notifications(
    db: DbSession,
    limit: int = Query(30, ge=1, le=200),
    kind: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
) -> list[NotificationOut]:
    query = (
        select(Notification, Product)
        .join(Product, Product.id == Notification.product_id)
        .order_by(Notification.sent_at.desc())
        .limit(limit)
    )
    if kind:
        query = query.where(Notification.kind == kind)
    if status_filter:
        query = query.where(Notification.status == status_filter)

    rows = db.execute(query).all()
    return [
        NotificationOut(
            id=notification.id,
            product_id=notification.product_id,
            product_title=product.title,
            product_url=product.url,
            shop=product.shop,
            price=to_float(notification.price),
            kind=notification.kind,
            channel=notification.channel,
            status=notification.status,
            message=notification.message,
            sent_at=as_utc(notification.sent_at),
        )
        for notification, product in rows
    ]


@router.get("/health", response_model=HealthOut)
def health(db: DbSession) -> HealthOut:
    database_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"
    return HealthOut(
        status="ok" if database_status == "ok" else "degraded",
        app=settings.app_name,
        environment=settings.environment,
        database=database_status,
        scheduler="running" if scheduler.running else "stopped",
        time=utcnow(),
    )
