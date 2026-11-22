"""Telegram command handlers: /start, /list, /add, /check and friends."""

from __future__ import annotations

import logging
from decimal import Decimal
from html import escape
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.bot.client import TelegramAPI
from app.config import settings
from app.database import SessionLocal
from app.models.models import PRODUCT_ACTIVE, PRODUCT_PAUSED, Product, User
from app.parsers import ParserError
from app.schemas import ProductCreate
from app.services.export import build_history_csv
from app.services.notifier import format_money
from app.services.price_service import (
    DuplicateProductError,
    check_all,
    check_product,
    create_product,
    get_or_create_telegram_user,
)
from app.services.stats import build_stats, get_history, to_float

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    PRODUCT_ACTIVE: "🟢 активен",
    PRODUCT_PAUSED: "⏸ пауза",
    "error": "⚠️ ошибка",
}

COMMANDS_HELP = """<b>Что я умею</b>

/add &lt;ссылка&gt; [цель] [скидка %] — добавить товар
/list — мои товары
/check [id|all] — проверить цены
/stats &lt;id&gt; — статистика и скидка
/target &lt;id&gt; &lt;цена|off&gt; — изменить цель
/pause &lt;id&gt; — поставить на паузу
/resume &lt;id&gt; — возобновить
/export &lt;id&gt; — CSV с историей
/delete &lt;id&gt; — удалить товар
/id — мой Telegram ID
/help — эта справка

Ссылку можно отправить и без команды — я попробую добавить её как товар."""


def parse_command(text: str) -> tuple[str, list[str]]:
    """``/list@PricePulseBot`` -> ``("list", [])``."""
    text = text.strip()
    if not text.startswith("/"):
        return "", []
    head, *args = text.split()
    return head[1:].split("@", 1)[0].lower(), args


def _display_name(tg_user: dict[str, Any]) -> str:
    parts = [tg_user.get("first_name"), tg_user.get("last_name")]
    name = " ".join(part for part in parts if part).strip()
    return name or tg_user.get("username") or "Telegram user"


def _parse_id(raw: str) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _parse_money(raw: str) -> float | None:
    try:
        value = float(raw.replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


class BotHandlers:
    """All update handling lives here so it can be tested with a fake API."""

    def __init__(self, api: TelegramAPI) -> None:
        self.api = api

    # ------------------------------------------------------------------ routing
    async def handle_update(self, update: dict[str, Any]) -> None:
        if "message" in update:
            await self._on_message(update["message"])
        elif "callback_query" in update:
            await self._on_callback(update["callback_query"])

    async def _on_message(self, message: dict[str, Any]) -> None:
        text = (message.get("text") or "").strip()
        if not text:
            return
        chat_id = (message.get("chat") or {}).get("id")
        tg_user = message.get("from") or {}
        user_id = tg_user.get("id")
        if chat_id is None or user_id is None:
            return

        if not self._allowed(user_id):
            await self.api.send_message(chat_id, self._denied(user_id))
            return

        command, args = parse_command(text)
        if not command:
            if text.startswith(("http://", "https://")):
                await self._cmd_add(chat_id, user_id, tg_user, [text])
            return

        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            await self.api.send_message(
                chat_id, "Неизвестная команда. Открой /help, чтобы увидеть список."
            )
            return
        await handler(chat_id, user_id, tg_user, args)

    async def _on_callback(self, callback: dict[str, Any]) -> None:
        data = callback.get("data") or ""
        message = callback.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        message_id = message.get("message_id")
        tg_user = callback.get("from") or {}
        user_id = tg_user.get("id")
        if chat_id is None or user_id is None:
            return

        try:
            if not self._allowed(user_id):
                await self.api.answer_callback_query(
                    callback["id"], self._denied(user_id), show_alert=True
                )
                return

            action, _, arg = data.partition(":")
            if action == "check_all":
                await self._cmd_check(chat_id, user_id, tg_user, ["all"])
            elif action == "list":
                await self._cmd_list(chat_id, user_id, tg_user, [])
            elif action in {"check", "stats", "pause", "resume", "del"}:
                await getattr(self, f"_cmd_{action}")(chat_id, user_id, tg_user, [arg])
            elif action == "delok":
                await self._delete_confirmed(chat_id, user_id, message_id, arg)
            elif action == "delno" and message_id is not None:
                await self.api.edit_message_text(
                    chat_id,
                    message_id,
                    "Удаление отменено.",
                    reply_markup={"inline_keyboard": []},
                )
            else:
                await self.api.answer_callback_query(callback["id"], "Кнопка устарела")
                return
        finally:
            try:
                await self.api.answer_callback_query(callback["id"])
            except Exception:  # pragma: no cover - Telegram may expire the query
                logger.debug("Could not answer callback query", exc_info=True)

    # ------------------------------------------------------------------ helpers
    def _allowed(self, user_id: int) -> bool:
        allowed = settings.telegram_allowed_id_set
        return not allowed or user_id in allowed

    @staticmethod
    def _denied(user_id: int) -> str:
        return (
            "⛔ Доступ к боту ограничен.\n"
            f"Ваш Telegram ID: <code>{user_id}</code>\n"
            "Передайте его администратору, чтобы получить доступ."
        )

    @staticmethod
    def _user(db: Session, tg_user: dict[str, Any]) -> User:
        return get_or_create_telegram_user(db, int(tg_user["id"]), _display_name(tg_user))

    @staticmethod
    def _product(db: Session, user: User, product_id: int) -> Product | None:
        return db.scalar(
            select(Product).where(Product.id == product_id, Product.user_id == user.id)
        )

    @staticmethod
    def _dashboard_url() -> str:
        return settings.public_base_url.rstrip("/") or "http://localhost:8000"

    @staticmethod
    def _status(product: Product) -> str:
        return STATUS_LABELS.get(product.status, product.status)

    def _product_keyboard(self, product: Product) -> dict[str, Any]:
        paused = product.status == PRODUCT_PAUSED
        toggle = {
            "text": "▶️ Возобновить" if paused else "⏸ Пауза",
            "callback_data": f"{'resume' if paused else 'pause'}:{product.id}",
        }
        return {
            "inline_keyboard": [
                [
                    {"text": "🔄 Проверить", "callback_data": f"check:{product.id}"},
                    {"text": "📊 Статистика", "callback_data": f"stats:{product.id}"},
                ],
                [toggle, {"text": "🗑 Удалить", "callback_data": f"del:{product.id}"}],
            ]
        }

    def _product_card(self, product: Product) -> str:
        target = to_float(product.target_price)
        line = f"Сейчас: <b>{format_money(to_float(product.last_price), product.currency)}</b>"
        if target is not None:
            line += f" · цель {format_money(target, product.currency)}"
        return (
            f'<b>#{product.id}</b> · <a href="{escape(product.url)}">'
            f"{escape(product.title[:120])}</a>\n"
            f"{line}\n{escape(product.shop)} · {self._status(product)}"
        )

    # ------------------------------------------------------------------ commands
    async def _cmd_start(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], _args: list[str]
    ) -> None:
        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            name = escape(user.display_name)
        finally:
            db.close()
        await self.api.send_message(
            chat_id,
            f"👋 <b>Привет, {name}!</b>\n\n"
            "Я PricePulse — слежу за ценами и пишу, когда товар дешевеет.\n\n"
            f"{COMMANDS_HELP}",
            reply_markup={
                "inline_keyboard": [
                    [{"text": "📋 Мои товары", "callback_data": "list"}],
                    [{"text": "🌐 Дашборд", "url": self._dashboard_url()}],
                ]
            },
        )

    async def _cmd_help(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], _args: list[str]
    ) -> None:
        await self.api.send_message(chat_id, COMMANDS_HELP)

    async def _cmd_id(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], _args: list[str]
    ) -> None:
        await self.api.send_message(
            chat_id,
            "🪪 <b>Ваши идентификаторы</b>\n"
            f"Telegram ID: <code>{user_id}</code>\n"
            f"Chat ID: <code>{chat_id}</code>\n\n"
            "Добавьте ID в <code>TELEGRAM_ALLOWED_USER_IDS</code>, чтобы ограничить доступ.",
        )

    async def _cmd_cancel(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], _args: list[str]
    ) -> None:
        await self.api.send_message(chat_id, "Нечего отменять — все команды выполняются сразу.")

    async def _cmd_list(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], _args: list[str]
    ) -> None:
        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            total = db.scalar(select(func.count(Product.id)).where(Product.user_id == user.id)) or 0
            products = list(
                db.scalars(
                    select(Product)
                    .where(Product.user_id == user.id)
                    .order_by(Product.created_at.desc())
                    .limit(20)
                ).all()
            )
        finally:
            db.close()

        if not products:
            await self.api.send_message(
                chat_id,
                "📭 Пока пусто.\n\n"
                f"Добавьте первый товар:\n<code>/add {self._dashboard_url()}"
                "/demo/shop/aurora-headphones 22000</code>",
            )
            return

        lines = [f"📋 <b>Ваши товары</b> · {total}", ""]
        for product in products:
            target = to_float(product.target_price)
            price = format_money(to_float(product.last_price), product.currency)
            suffix = f" · цель {format_money(target, product.currency)}" if target else ""
            lines.append(
                f'<b>#{product.id}</b> · <a href="{escape(product.url)}">'
                f"{escape(product.title[:80])}</a>\n"
                f"{price}{suffix} · {self._status(product)}"
            )
        if total > len(products):
            lines.append(f"…и ещё {total - len(products)}. Полный список — в дашборде.")

        await self.api.send_message(
            chat_id,
            "\n".join(lines),
            reply_markup={
                "inline_keyboard": [
                    [{"text": "🔄 Проверить все", "callback_data": "check_all"}],
                    [{"text": "🌐 Дашборд", "url": self._dashboard_url()}],
                ]
            },
        )

    async def _cmd_add(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        if not args:
            await self.api.send_message(
                chat_id,
                "Формат: <code>/add &lt;ссылка&gt; [цель] [скидка %]</code>\n"
                f"Пример: <code>/add {self._dashboard_url()}"
                "/demo/shop/aurora-headphones 22000 10</code>",
            )
            return

        url = args[0].strip()
        if not url.startswith(("http://", "https://")):
            await self.api.send_message(chat_id, "Ссылка должна начинаться с http:// или https://")
            return

        target = None
        if len(args) > 1:
            target = _parse_money(args[1])
            if target is None:
                await self.api.send_message(chat_id, "Цель должна быть неотрицательным числом.")
                return

        discount = None
        if len(args) > 2:
            try:
                discount = int(args[2].rstrip("%"))
            except ValueError:
                await self.api.send_message(chat_id, "Скидка должна быть целым числом от 1 до 90.")
                return

        status_message = await self.api.send_message(chat_id, "⏳ Проверяю ссылку…")
        message_id = status_message.get("message_id")

        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            payload = ProductCreate(
                url=url,
                target_price=target,
                target_discount_percent=discount,
            )
            product = await create_product(db, payload, user=user)
        except DuplicateProductError:
            text = "Этот товар уже отслеживается. Посмотрите /list."
        except ParserError as exc:
            text = f"⚠️ Не удалось разобрать страницу:\n{escape(str(exc))}"
        except ValidationError as exc:
            text = f"⚠️ Некорректные данные: {escape(str(exc.errors()[0].get('msg', 'ошибка')))}"
        except Exception:
            logger.exception("Bot failed to add product %s", url)
            text = "⚠️ Не удалось добавить товар. Проверьте ссылку и попробуйте ещё раз."
        else:
            text = f"✅ <b>Добавлено</b>\n\n{self._product_card(product)}"
            if message_id is not None:
                await self.api.edit_message_text(
                    chat_id,
                    message_id,
                    text,
                    reply_markup=self._product_keyboard(product),
                )
                return
        finally:
            db.close()

        if message_id is not None:
            await self.api.edit_message_text(chat_id, message_id, text)
        else:  # pragma: no cover - Telegram always returns message_id
            await self.api.send_message(chat_id, text)

    async def _cmd_check(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            if args and args[0].lower() != "all":
                product_id = _parse_id(args[0])
                product = self._product(db, user, product_id) if product_id else None
                if product is None:
                    await self.api.send_message(chat_id, "Товар не найден. Посмотрите /list.")
                    return

                status_message = await self.api.send_message(
                    chat_id, f"⏳ Проверяю «{escape(product.title[:80])}»…"
                )
                result = await check_product(db, product, force=True)
                text = self._format_result(result)
            else:
                ids = list(db.scalars(select(Product.id).where(Product.user_id == user.id)).all())
                if not ids:
                    await self.api.send_message(chat_id, "📭 Нет товаров для проверки.")
                    return
                status_message = await self.api.send_message(
                    chat_id, f"⏳ Проверяю {len(ids)} товар(ов)…"
                )
                summary = await check_all(db, force=True, product_ids=ids)
                text = self._format_summary(summary)
        finally:
            db.close()

        message_id = status_message.get("message_id")
        if message_id is not None:
            await self.api.edit_message_text(chat_id, message_id, text)
        else:  # pragma: no cover
            await self.api.send_message(chat_id, text)

    async def _cmd_stats(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        product_id = _parse_id(args[0]) if args else None
        if product_id is None:
            await self.api.send_message(chat_id, "Формат: <code>/stats &lt;id&gt;</code>")
            return

        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            product = self._product(db, user, product_id)
            if product is None:
                await self.api.send_message(chat_id, "Товар не найден. Посмотрите /list.")
                return
            stats = build_stats(db, product)
            points = len(get_history(db, product.id))
        finally:
            db.close()

        currency = product.currency
        current = stats["current_price"]
        median = stats["median_30d"]
        discount = (
            round((1 - current / median) * 100, 1) if current is not None and median else None
        )
        delta = stats["delta_24h"]
        delta_line = "—"
        if delta is not None:
            delta_line = f"{'+' if delta > 0 else ''}{format_money(delta, currency)}"
            if stats["delta_percent_24h"] is not None:
                delta_line += f" ({stats['delta_percent_24h']:+.1f}%)"

        lines = [
            f"📊 <b>{escape(product.title[:120])}</b>",
            f"Сейчас: <b>{format_money(current, currency)}</b>",
            f"За 24 часа: {delta_line}",
            f"Мин / макс: {format_money(stats['min_price'], currency)} / "
            f"{format_money(stats['max_price'], currency)}",
            f"Средняя: {format_money(stats['avg_price'], currency)}",
            f"Медиана 30 дней: {format_money(median, currency)}",
        ]
        if discount is not None:
            lines.append(f"Скидка к медиане: <b>{discount:+.1f}%</b>")
        if product.target_price is not None:
            lines.append(f"Цель: {format_money(to_float(product.target_price), currency)}")
        lines.append(f"Точек истории: {points}")
        lines.append(f"Статус: {self._status(product)}")

        await self.api.send_message(
            chat_id,
            "\n".join(lines),
            reply_markup={
                "inline_keyboard": [[{"text": "🌐 Открыть дашборд", "url": self._dashboard_url()}]]
            },
        )

    async def _cmd_pause(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        await self._set_status(chat_id, tg_user, args, PRODUCT_PAUSED)

    async def _cmd_resume(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        await self._set_status(chat_id, tg_user, args, PRODUCT_ACTIVE)

    async def _set_status(
        self, chat_id: int, tg_user: dict[str, Any], args: list[str], status: str
    ) -> None:
        product_id = _parse_id(args[0]) if args else None
        if product_id is None:
            await self.api.send_message(chat_id, "Укажите id товара. Посмотрите /list.")
            return

        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            product = self._product(db, user, product_id)
            if product is None:
                await self.api.send_message(chat_id, "Товар не найден. Посмотрите /list.")
                return
            product.status = status
            if status == PRODUCT_ACTIVE:
                product.error_count = 0
                product.last_error = None
            db.commit()
            db.refresh(product)
        finally:
            db.close()

        action = "возобновлён" if status == PRODUCT_ACTIVE else "поставлен на паузу"
        await self.api.send_message(
            chat_id,
            f"✅ Товар <b>#{product.id}</b> {action}.\n\n{self._product_card(product)}",
            reply_markup=self._product_keyboard(product),
        )

    async def _cmd_target(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        if len(args) < 2:
            await self.api.send_message(
                chat_id, "Формат: <code>/target &lt;id&gt; &lt;цена|off&gt;</code>"
            )
            return
        product_id = _parse_id(args[0])
        raw = args[1].lower()
        value: float | None
        if raw in {"off", "none", "нет", "0"}:
            value = None
        else:
            value = _parse_money(args[1])
            if value is None or value <= 0:
                await self.api.send_message(
                    chat_id, "Цена должна быть положительным числом или off."
                )
                return

        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            product = self._product(db, user, product_id) if product_id else None
            if product is None:
                await self.api.send_message(chat_id, "Товар не найден. Посмотрите /list.")
                return
            product.target_price = (
                Decimal(str(value)).quantize(Decimal("0.01")) if value is not None else None
            )
            db.commit()
            db.refresh(product)
        finally:
            db.close()

        if value is None:
            text = f"🎯 Цель для <b>#{product.id}</b> снята."
        else:
            text = f"🎯 Цель для <b>#{product.id}</b>: " f"{format_money(value, product.currency)}."
        await self.api.send_message(chat_id, text, reply_markup=self._product_keyboard(product))

    async def _cmd_delete(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        product_id = _parse_id(args[0]) if args else None
        if product_id is None:
            await self.api.send_message(chat_id, "Формат: <code>/delete &lt;id&gt;</code>")
            return

        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            product = self._product(db, user, product_id)
            if product is None:
                await self.api.send_message(chat_id, "Товар не найден. Посмотрите /list.")
                return
            title = escape(product.title[:120])
        finally:
            db.close()

        await self.api.send_message(
            chat_id,
            f"Удалить <b>{title}</b> вместе с историей цен?",
            reply_markup={
                "inline_keyboard": [
                    [
                        {"text": "🗑 Да, удалить", "callback_data": f"delok:{product_id}"},
                        {"text": "Отмена", "callback_data": "delno"},
                    ]
                ]
            },
        )

    async def _delete_confirmed(
        self, chat_id: int, user_id: int, message_id: int | None, raw_id: str
    ) -> None:
        product_id = _parse_id(raw_id)
        db = SessionLocal()
        try:
            user = db.scalar(select(User).where(User.telegram_id == user_id))
            product = self._product(db, user, product_id) if user and product_id else None
            if product is None:
                text = "Товар уже удалён."
            else:
                title = escape(product.title[:120])
                db.delete(product)
                db.commit()
                text = f"🗑 Удалено: <b>{title}</b>"
        finally:
            db.close()

        if message_id is not None:
            await self.api.edit_message_text(
                chat_id, message_id, text, reply_markup={"inline_keyboard": []}
            )
        else:  # pragma: no cover
            await self.api.send_message(chat_id, text)

    async def _cmd_export(
        self, chat_id: int, user_id: int, tg_user: dict[str, Any], args: list[str]
    ) -> None:
        product_id = _parse_id(args[0]) if args else None
        if product_id is None:
            await self.api.send_message(chat_id, "Формат: <code>/export &lt;id&gt;</code>")
            return

        db = SessionLocal()
        try:
            user = self._user(db, tg_user)
            product = self._product(db, user, product_id)
            if product is None:
                await self.api.send_message(chat_id, "Товар не найден. Посмотрите /list.")
                return
            rows = get_history(db, product.id, days=365)
            if not rows:
                await self.api.send_message(chat_id, "История пока пуста.")
                return
            filename, content = build_history_csv(product, rows)
            caption = f"📄 История цен: {escape(product.title[:100])} ({len(rows)} точек)"
        finally:
            db.close()

        await self.api.send_document(chat_id, filename, content, caption=caption)

    # ------------------------------------------------------------------ formatting
    @staticmethod
    def _format_result(result: Any) -> str:
        title = escape(result.title[:100])
        if result.status == "ok":
            if result.changed and result.old_price is not None:
                return (
                    f"✅ <b>{title}</b>\n"
                    f"{format_money(result.old_price)} → <b>{format_money(result.price)}</b>"
                )
            return f"✅ <b>{title}</b>\nЦена не изменилась: {format_money(result.price)}"
        if result.status == "skipped":
            return f"⏸ <b>{title}</b>\n{escape(result.skipped_reason or 'Проверка пропущена')}"
        return f"⚠️ <b>{title}</b>\n{escape(result.error or 'Не удалось проверить товар')}"

    @staticmethod
    def _format_summary(summary: Any) -> str:
        if not summary.results:
            return "⏳ Проверка уже выполняется. Попробуйте через минуту."
        lines = [
            f"✅ <b>Проверка завершена</b> за {summary.duration_seconds:.1f} с",
            f"Проверено: {summary.checked} · изменилось: {summary.changed} · "
            f"ошибок: {summary.failed} · пропущено: {summary.skipped}",
        ]
        if summary.notifications:
            lines.append(f"🔔 Уведомлений: {summary.notifications}")
        lines.append("")
        for result in summary.results[:12]:
            title = escape(result.title[:60])
            if result.status == "ok" and result.changed:
                lines.append(
                    f"• <b>{title}</b>: {format_money(result.old_price)} → "
                    f"{format_money(result.price)}"
                )
            elif result.status == "error":
                lines.append(f"• ⚠️ {title}: {escape((result.error or '')[:100])}")
            elif result.status == "skipped":
                lines.append(f"• ⏸ {title}: пропущено")
        if len(summary.results) > 12:
            lines.append(f"…и ещё {len(summary.results) - 12}.")
        return "\n".join(lines)
