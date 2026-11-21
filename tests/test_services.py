"""Service-level tests: notifications, error handling and rate limiting."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest
from app.models.models import Notification, PriceHistory, Product, utcnow
from app.parsers.base import ParsedProduct, ParserError
from app.schemas import ProductCreate
from app.services import price_service
from app.services.notifier import build_message, format_money
from sqlalchemy import select


def run(coro):
    """Run an async service coroutine from a synchronous test."""
    return asyncio.run(coro)


async def allowed(_url: str):
    return True, None


def make_product(
    db,
    *,
    target: Decimal | None = None,
    discount: int | None = None,
    price: str = "1000",
) -> Product:
    user = price_service.get_or_create_default_user(db)
    product = Product(
        user_id=user.id,
        url="https://example.com/demo/shop/service-test",
        shop="demo",
        title="Сервисный товар",
        currency="RUB",
        target_price=target,
        target_discount_percent=discount,
        status="active",
        last_price=Decimal(price),
        last_checked_at=utcnow(),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    db.add(
        PriceHistory(
            product_id=product.id,
            price=Decimal(price),
            currency="RUB",
            in_stock=True,
            checked_at=utcnow(),
        )
    )
    db.commit()
    return product


def fake_parse(price: float, title: str = "Сервисный товар"):
    async def _parse(_url: str) -> ParsedProduct:
        return ParsedProduct(
            title=title,
            price=price,
            currency="RUB",
            in_stock=True,
            image_url="/static/img/products/echo-speaker.svg",
            external_id="service-test",
            shop="demo",
        )

    return _parse


@pytest.fixture()
def quiet_telegram(monkeypatch):
    """Telegram is disabled in tests: notifications must be stored as skipped."""
    from app.config import settings

    monkeypatch.setattr(settings, "telegram_enabled", False)


def test_format_money_and_message():
    assert format_money(12990) == "12 990 ₽"
    assert format_money(99.5, "USD") == "100 $"
    assert format_money(None) == "—"

    product = SimpleNamespace(
        url="https://example.com/item",
        title="Aurora <Studio>",
        shop="demo",
        currency="RUB",
        target_price=Decimal("20000"),
        last_price=Decimal("19000"),
        last_error=None,
    )
    message = build_message(product, "target", Decimal("19000"), "Ниже цели на 1 000 ₽")
    assert "Цена достигла цели" in message
    assert "Aurora &lt;Studio&gt;" in message
    assert "19 000 ₽" in message
    assert "цель 20 000 ₽" in message


def test_target_notification_is_persisted_as_skipped(db, quiet_telegram):
    product = make_product(db, target=Decimal("1200"))

    notifications = run(price_service._evaluate_notifications(db, product, 1000.0, old_price=None))
    db.commit()

    rows = list(db.scalars(select(Notification)).all())
    assert notifications == 1
    assert len(rows) == 1
    assert rows[0].kind == "target"
    assert rows[0].channel == "telegram"
    assert rows[0].status == "skipped"
    assert rows[0].product_id == product.id


def test_target_notification_is_not_duplicated_within_24h(db, quiet_telegram):
    product = make_product(db, target=Decimal("1200"))
    run(price_service._evaluate_notifications(db, product, 1000.0, old_price=None))
    db.commit()

    # Second evaluation inside the cooldown window: nothing new.
    sent = run(price_service._evaluate_notifications(db, product, 900.0, old_price=None))
    db.commit()

    rows = list(db.scalars(select(Notification)).all())
    assert sent == 0
    assert len(rows) == 1


def test_discount_notification_uses_median(db, quiet_telegram):
    product = make_product(db, discount=10)
    # 30 days of history around 2000 so the median is well above the new price.
    for _day in range(5):
        db.add(
            PriceHistory(
                product_id=product.id,
                price=Decimal("2000"),
                currency="RUB",
                in_stock=True,
                checked_at=utcnow(),
            )
        )
    db.commit()

    sent = run(price_service._evaluate_notifications(db, product, 1500.0, old_price=2000.0))
    db.commit()

    rows = list(db.scalars(select(Notification)).all())
    kinds = {row.kind for row in rows}
    assert sent >= 1
    assert "discount" in kinds


def test_price_drop_notification(db, quiet_telegram):
    product = make_product(db)
    sent = run(price_service._evaluate_notifications(db, product, 900.0, old_price=1000.0))
    db.commit()

    rows = list(db.scalars(select(Notification)).all())
    assert sent == 1
    assert rows[0].kind == "price_drop"


def test_product_marked_error_after_threshold(db, monkeypatch, quiet_telegram):
    product = make_product(db)
    product.last_checked_at = None
    db.commit()

    async def broken(_url: str):
        raise ParserError("Страница недоступна")

    monkeypatch.setattr(price_service, "get_parser", lambda _url: SimpleNamespace(parse=broken))
    monkeypatch.setattr(price_service, "robots_allowed", allowed)

    results = [run(price_service.check_product(db, product, force=True)) for _ in range(3)]

    assert [result.status for result in results] == ["error", "error", "error"]
    db.refresh(product)
    assert product.error_count == 3
    assert product.status == "error"
    assert "недоступна" in (product.last_error or "")

    rows = list(db.scalars(select(Notification)).all())
    assert [row.kind for row in rows].count("error") == 1


def test_error_notification_is_sent_once(db, monkeypatch, quiet_telegram):
    product = make_product(db)
    product.last_checked_at = None
    db.commit()

    async def broken(_url: str):
        raise ParserError("boom")

    monkeypatch.setattr(price_service, "get_parser", lambda _url: SimpleNamespace(parse=broken))
    monkeypatch.setattr(price_service, "robots_allowed", allowed)

    for _ in range(5):
        run(price_service.check_product(db, product, force=True))

    rows = list(db.scalars(select(Notification)).all())
    assert [row.kind for row in rows].count("error") == 1


def test_recent_check_is_skipped(db):
    product = make_product(db)
    product.last_checked_at = utcnow()
    db.commit()

    result = run(price_service.check_product(db, product, force=False))

    assert result.status == "skipped"
    assert result.skipped_reason is not None
    assert "лимит" in result.skipped_reason


def test_successful_check_records_history_and_resets_errors(db, monkeypatch):
    product = make_product(db)
    product.error_count = 2
    product.last_error = "старая ошибка"
    product.last_checked_at = None
    db.commit()

    monkeypatch.setattr(
        price_service, "get_parser", lambda _url: SimpleNamespace(parse=fake_parse(800.0))
    )
    monkeypatch.setattr(price_service, "robots_allowed", allowed)

    result = run(price_service.check_product(db, product, force=True))

    assert result.status == "ok"
    assert result.changed is True
    assert result.price == 800.0
    db.refresh(product)
    assert product.error_count == 0
    assert product.last_error is None
    assert product.status == "active"

    prices = [
        float(row.price)
        for row in db.scalars(
            select(PriceHistory)
            .where(PriceHistory.product_id == product.id)
            .order_by(PriceHistory.checked_at)
        ).all()
    ]
    assert prices[-1] == 800.0


def test_create_product_triggers_target_notification(db, monkeypatch, quiet_telegram):
    async def parse(_url: str):
        return ParsedProduct(title="Новый товар", price=1000.0, shop="demo")

    monkeypatch.setattr(price_service, "parse_product", parse)

    product = run(
        price_service.create_product(
            db,
            ProductCreate(url="https://example.com/demo/shop/new", target_price=1200),
        )
    )

    rows = list(db.scalars(select(Notification)).all())
    assert len(rows) == 1
    assert rows[0].kind == "target"
    assert product.last_price == Decimal("1000.00")
