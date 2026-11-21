"""Telegram notifications (with a safe demo mode)."""

from __future__ import annotations

import logging
from decimal import Decimal
from html import escape

import httpx

from app.config import settings
from app.models.models import Notification, Product
from app.services.stats import to_float

logger = logging.getLogger(__name__)

KIND_TITLES = {
    "target": "🎯 Цена достигла цели",
    "discount": "🔥 Настоящая скидка",
    "price_drop": "📉 Цена снизилась",
    "error": "⚠️ Товар не проверяется",
}


def format_money(value: float | None, currency: str = "RUB") -> str:
    if value is None:
        return "—"
    symbol = {"RUB": "₽", "USD": "$", "EUR": "€"}.get(currency, currency)
    return f"{value:,.0f}".replace(",", " ") + f" {symbol}"


def build_message(product: Product, kind: str, price: Decimal | None, extra: str = "") -> str:
    headline = KIND_TITLES.get(kind, "Обновление цены")
    current = to_float(price) if price is not None else to_float(product.last_price)
    lines = [
        f"<b>{headline}</b>",
        f'<a href="{escape(product.url)}">{escape(product.title)}</a>',
    ]
    if kind == "error":
        lines.append(extra or escape(product.last_error or "Неизвестная ошибка"))
    else:
        price_line = f"Сейчас: <b>{format_money(current, product.currency)}</b>"
        if product.target_price is not None:
            price_line += (
                f" · цель {format_money(to_float(product.target_price), product.currency)}"
            )
        lines.append(price_line)
        if extra:
            lines.append(extra)
    lines.append(f"<i>{escape(product.shop)} · PricePulse</i>")
    return "\n".join(lines)


class NotificationService:
    """Persists every notification and delivers it to Telegram when configured."""

    async def send(
        self,
        product: Product,
        kind: str,
        *,
        price: Decimal | None = None,
        extra: str = "",
    ) -> Notification:
        message = build_message(product, kind, price, extra)
        notification = Notification(
            product_id=product.id,
            price=price if price is not None else product.last_price,
            kind=kind,
            channel="telegram",
            message=message,
            status="skipped",
        )

        chat_id = str(product.user.telegram_id or settings.telegram_chat_id or "")
        if not settings.telegram_enabled:
            notification.status = "skipped"
            logger.info("Telegram disabled, notification stored only: %s", product.title)
            return notification
        if not settings.telegram_bot_token or not chat_id:
            notification.status = "skipped"
            logger.info(
                "Telegram is not configured (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID), "
                "notification stored only: %s",
                product.title,
            )
            return notification

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": False,
                    },
                )
            if response.status_code == 200 and response.json().get("ok"):
                notification.status = "sent"
                logger.info("Telegram notification sent: %s (%s)", product.title, kind)
            else:
                notification.status = "failed"
                logger.error("Telegram API error %s: %s", response.status_code, response.text[:300])
        except httpx.HTTPError as exc:
            notification.status = "failed"
            logger.error("Telegram request failed: %s", exc)

        return notification
