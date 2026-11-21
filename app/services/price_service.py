"""Core business logic: add products, check prices, trigger notifications."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import (
    PRODUCT_ACTIVE,
    PRODUCT_ERROR,
    Notification,
    PriceHistory,
    Product,
    User,
    utcnow,
)
from app.parsers import ParserError, get_parser, parse_product
from app.schemas import CheckResult, CheckSummary, ProductCreate
from app.services.notifier import NotificationService, format_money
from app.services.robots import robots_allowed
from app.services.stats import _median_30d, as_utc, to_float

logger = logging.getLogger(__name__)

_running = False


class DuplicateProductError(ValueError):
    pass


def _money(value: float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.01"))


def get_or_create_default_user(db: Session) -> User:
    user = db.scalar(select(User).order_by(User.id).limit(1))
    if user is None:
        user = User(
            display_name="PricePulse demo",
            telegram_id=settings.default_user_telegram_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _latest_price(db: Session, product_id: int) -> float | None:
    row = db.scalar(
        select(PriceHistory)
        .where(PriceHistory.product_id == product_id)
        .order_by(PriceHistory.checked_at.desc())
        .limit(1)
    )
    return float(row.price) if row else None


def _recent_notification(db: Session, product_id: int, kind: str, hours: int) -> bool:
    since = utcnow() - timedelta(hours=hours)
    row = db.scalar(
        select(Notification.id)
        .where(Notification.product_id == product_id)
        .where(Notification.kind == kind)
        .where(Notification.sent_at >= since)
        .limit(1)
    )
    return row is not None


async def create_product(db: Session, payload: ProductCreate) -> Product:
    """Parse the URL and start tracking it. Raises ParserError on bad pages."""
    user = get_or_create_default_user(db)
    duplicate = db.scalar(
        select(Product).where(Product.user_id == user.id, Product.url == payload.url)
    )
    if duplicate is not None:
        raise DuplicateProductError("Этот товар уже отслеживается")

    parsed = await parse_product(payload.url)
    product = Product(
        user_id=user.id,
        url=payload.url,
        shop=parsed.shop,
        external_id=parsed.external_id,
        title=parsed.title,
        image_url=parsed.image_url,
        currency=parsed.currency,
        target_price=_money(payload.target_price),
        target_discount_percent=payload.target_discount_percent,
        status=PRODUCT_ACTIVE,
        last_price=_money(parsed.price),
        last_checked_at=utcnow(),
    )
    db.add(product)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateProductError("Этот товар уже отслеживается") from exc

    db.add(
        PriceHistory(
            product_id=product.id,
            price=_money(parsed.price),
            currency=parsed.currency,
            in_stock=parsed.in_stock,
            checked_at=utcnow(),
        )
    )
    db.commit()
    db.refresh(product)

    await _evaluate_notifications(db, product, parsed.price, old_price=None)
    db.commit()
    logger.info("Tracking started: %s (%s, %.2f)", product.title, product.shop, parsed.price)
    return product


async def _evaluate_notifications(
    db: Session,
    product: Product,
    price: float,
    old_price: float | None,
    notifier: NotificationService | None = None,
) -> int:
    notifier = notifier or NotificationService()
    sent = 0
    target = to_float(product.target_price)

    if target is not None and price <= target:
        crossed = old_price is None or old_price > target
        if crossed and not _recent_notification(db, product.id, "target", 24):
            saving = target - price
            extra = f"Ниже цели на {format_money(saving, product.currency)}"
            notification = await notifier.send(product, "target", price=_money(price), extra=extra)
            db.add(notification)
            sent += 1

    if product.target_discount_percent:
        median_price = _median_30d(db, product.id)
        if median_price and price < median_price:
            discount = round((1 - price / median_price) * 100, 1)
            if discount >= product.target_discount_percent and not _recent_notification(
                db, product.id, "discount", 24 * 7
            ):
                extra = (
                    f"Скидка {discount:.0f}% к медиане 30 дней "
                    f"({format_money(median_price, product.currency)})"
                )
                notification = await notifier.send(
                    product, "discount", price=_money(price), extra=extra
                )
                db.add(notification)
                sent += 1

    if old_price and price < old_price:
        drop = (old_price - price) / old_price * 100
        if drop >= 8 and not _recent_notification(db, product.id, "price_drop", 24):
            extra = f"Было {format_money(old_price, product.currency)} · −{drop:.0f}%"
            notification = await notifier.send(
                product, "price_drop", price=_money(price), extra=extra
            )
            db.add(notification)
            sent += 1

    return sent


async def _notify_error(db: Session, product: Product, error: str) -> int:
    if not _recent_notification(db, product.id, "error", 24):
        notification = await NotificationService().send(product, "error", extra=error)
        db.add(notification)
        return 1
    return 0


async def check_product(
    db: Session,
    product: Product,
    *,
    force: bool = False,
    notifier: NotificationService | None = None,
) -> CheckResult:
    """Check one product, persist history and return a compact result."""
    now = utcnow()
    last_checked = as_utc(product.last_checked_at)
    if (
        not force
        and last_checked is not None
        and now - last_checked < timedelta(minutes=settings.min_check_interval_minutes)
    ):
        return CheckResult(
            product_id=product.id,
            title=product.title,
            status="skipped",
            price=to_float(product.last_price),
            skipped_reason=(
                f"Проверено {int((now - last_checked).total_seconds() // 60)} мин назад "
                f"(лимит {settings.min_check_interval_minutes} мин)"
            ),
        )

    old_price = _latest_price(db, product.id)
    try:
        allowed, reason = await robots_allowed(product.url)
        if not allowed:
            raise ParserError(reason or "robots.txt запрещает обход страницы")

        parser = get_parser(product.url)
        parsed = await parser.parse(product.url)
    except Exception as exc:
        message = str(exc)[:500] or exc.__class__.__name__
        product.error_count += 1
        product.last_error = message
        product.last_checked_at = now
        logger.warning(
            "Check failed for #%s %s (%s/%s): %s",
            product.id,
            product.title,
            product.error_count,
            settings.error_threshold,
            message,
        )
        notifications = 0
        if product.error_count >= settings.error_threshold:
            product.status = PRODUCT_ERROR
            notifications = await _notify_error(db, product, message)
        db.commit()
        return CheckResult(
            product_id=product.id,
            title=product.title,
            status="error",
            price=to_float(product.last_price),
            error=message,
            notifications=notifications,
        )

    changed = old_price is None or round(old_price, 2) != round(parsed.price, 2)
    if changed:
        db.add(
            PriceHistory(
                product_id=product.id,
                price=_money(parsed.price),
                currency=parsed.currency,
                in_stock=parsed.in_stock,
                checked_at=now,
            )
        )

    product.title = parsed.title or product.title
    product.image_url = parsed.image_url or product.image_url
    product.external_id = parsed.external_id or product.external_id
    product.currency = parsed.currency
    product.last_price = _money(parsed.price)
    product.last_checked_at = now
    product.last_error = None
    product.error_count = 0
    if product.status == PRODUCT_ERROR:
        product.status = PRODUCT_ACTIVE
    db.flush()

    notifications = await _evaluate_notifications(db, product, parsed.price, old_price, notifier)
    db.commit()

    logger.info(
        "Checked #%s %s: %s -> %s (%s)",
        product.id,
        product.title,
        old_price,
        parsed.price,
        "changed" if changed else "same",
    )
    return CheckResult(
        product_id=product.id,
        title=product.title,
        status="ok",
        price=parsed.price,
        old_price=old_price,
        changed=changed,
        notifications=notifications,
    )


async def check_all(
    db: Session,
    *,
    force: bool = False,
    product_ids: list[int] | None = None,
    notifier: NotificationService | None = None,
) -> CheckSummary:
    """Check every active product sequentially, politely pausing between shops."""
    global _running
    started = time.perf_counter()
    if _running:
        return CheckSummary(
            checked=0,
            changed=0,
            failed=0,
            skipped=0,
            notifications=0,
            duration_seconds=0,
            results=[],
        )

    _running = True
    try:
        query = select(Product)
        if product_ids:
            query = query.where(Product.id.in_(product_ids))
        else:
            query = query.where(Product.status == PRODUCT_ACTIVE)
        products = list(db.scalars(query.order_by(Product.id)).all())

        results: list[CheckResult] = []
        for index, product in enumerate(products):
            result = await check_product(db, product, force=force, notifier=notifier)
            results.append(result)
            if index < len(products) - 1 and settings.request_delay_seconds:
                await asyncio.sleep(settings.request_delay_seconds)

        duration = round(time.perf_counter() - started, 2)
        summary = CheckSummary(
            checked=sum(1 for item in results if item.status == "ok"),
            changed=sum(1 for item in results if item.changed),
            failed=sum(1 for item in results if item.status == "error"),
            skipped=sum(1 for item in results if item.status == "skipped"),
            notifications=sum(item.notifications for item in results),
            duration_seconds=duration,
            results=results,
        )
        logger.info(
            "Check cycle finished in %ss: %s ok, %s changed, %s failed, %s skipped, %s notifications",
            duration,
            summary.checked,
            summary.changed,
            summary.failed,
            summary.skipped,
            summary.notifications,
        )
        return summary
    finally:
        _running = False
