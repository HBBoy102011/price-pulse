"""Price statistics and sparkline helpers."""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import PriceHistory, Product, utcnow


def to_float(value: Decimal | float | int | None) -> float | None:
    return round(float(value), 2) if value is not None else None


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def get_history(
    db: Session,
    product_id: int,
    *,
    days: int | None = None,
    limit: int | None = None,
) -> list[PriceHistory]:
    query = select(PriceHistory).where(PriceHistory.product_id == product_id)
    if days:
        query = query.where(PriceHistory.checked_at >= utcnow() - timedelta(days=days))
    query = query.order_by(PriceHistory.checked_at.asc())
    rows = list(db.scalars(query).all())
    if limit and len(rows) > limit:
        rows = _downsample(rows, limit)
    return rows


def _downsample(rows: list[PriceHistory], limit: int) -> list[PriceHistory]:
    if limit <= 2 or len(rows) <= limit:
        return rows
    step = (len(rows) - 1) / (limit - 1)
    indexes = {round(index * step) for index in range(limit)}
    indexes.add(len(rows) - 1)
    return [rows[index] for index in sorted(indexes)]


def _median_30d(db: Session, product_id: int, before: datetime | None = None) -> float | None:
    since = (before or utcnow()) - timedelta(days=30)
    prices = list(
        db.scalars(
            select(PriceHistory.price)
            .where(PriceHistory.product_id == product_id)
            .where(PriceHistory.checked_at >= since)
        ).all()
    )
    return round(float(median(prices)), 2) if prices else None


def build_stats(db: Session, product: Product, *, days: int | None = None) -> dict:
    rows = get_history(db, product.id, days=days)
    prices = [float(row.price) for row in rows]
    current = to_float(product.last_price)
    if current is None and prices:
        current = prices[-1]

    now = utcnow()
    recent = [
        (as_utc(row.checked_at), float(row.price))
        for row in rows
        if as_utc(row.checked_at) and as_utc(row.checked_at) >= now - timedelta(hours=24)
    ]
    if len(recent) >= 2:
        delta_24h = round(recent[-1][1] - recent[0][1], 2)
    elif len(prices) >= 2:
        delta_24h = round(prices[-1] - prices[-2], 2)
    else:
        delta_24h = 0.0 if prices else None

    delta_percent = None
    if delta_24h is not None and recent:
        base = recent[0][1]
        if base:
            delta_percent = round(delta_24h / base * 100, 1)

    change_count = 0
    for previous, current_row in itertools.pairwise(prices):
        if previous != current_row:
            change_count += 1

    target = to_float(product.target_price)
    below_target = bool(target is not None and current is not None and current <= target)
    savings = round(max(prices) - current, 2) if prices and current is not None else None

    progress = None
    if target is not None and current is not None and prices:
        peak = max(prices)
        if current <= target:
            progress = 100.0
        elif peak > target:
            progress = round(min(100, max(0, (peak - current) / (peak - target) * 100)), 1)

    return {
        "current_price": current,
        "min_price": round(min(prices), 2) if prices else None,
        "max_price": round(max(prices), 2) if prices else None,
        "avg_price": round(mean(prices), 2) if prices else None,
        "median_30d": _median_30d(db, product.id),
        "delta_24h": delta_24h,
        "delta_percent_24h": delta_percent,
        "change_count": change_count,
        "below_target": below_target,
        "savings_from_peak": savings,
        "target_progress": progress,
    }


def sparkline(db: Session, product_id: int, points: int = 22) -> list[float]:
    rows = get_history(db, product_id, days=45, limit=points)
    return [round(float(row.price), 2) for row in rows]


def card_payload(db: Session, product: Product) -> dict:
    stats = build_stats(db, product)
    return {
        "id": product.id,
        "url": product.url,
        "shop": product.shop,
        "external_id": product.external_id,
        "title": product.title,
        "image_url": product.image_url,
        "currency": product.currency,
        "target_price": to_float(product.target_price),
        "target_discount_percent": product.target_discount_percent,
        "status": product.status,
        "last_price": to_float(product.last_price),
        "last_checked_at": as_utc(product.last_checked_at),
        "last_error": product.last_error,
        "error_count": product.error_count,
        "created_at": as_utc(product.created_at),
        "current_price": stats["current_price"],
        "delta_24h": stats["delta_24h"],
        "delta_percent_24h": stats["delta_percent_24h"],
        "min_price": stats["min_price"],
        "max_price": stats["max_price"],
        "avg_price": stats["avg_price"],
        "median_30d": stats["median_30d"],
        "discount_percent": (
            round((1 - stats["current_price"] / stats["median_30d"]) * 100, 1)
            if stats["current_price"] and stats["median_30d"]
            else None
        ),
        "sparkline": sparkline(db, product.id),
        "history_points": len(get_history(db, product.id)),
        "below_target": stats["below_target"],
        "target_progress": stats["target_progress"],
        "savings_from_peak": stats["savings_from_peak"],
    }
