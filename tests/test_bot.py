"""Tests for the Telegram bot: routing, commands and callbacks."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from app.bot.handlers import BotHandlers, parse_command
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.models import Product, User
from app.parsers.base import ParsedProduct
from app.services import price_service
from sqlalchemy import select


def run(coro):
    return asyncio.run(coro)


class FakeAPI:
    """Records calls instead of talking to Telegram."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.edits: list[dict] = []
        self.callbacks: list[dict] = []
        self.documents: list[dict] = []
        self._message_id = 100

    async def send_message(
        self, chat_id, text, *, reply_markup=None, disable_web_page_preview=True
    ):
        self._message_id += 1
        self.messages.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        return {"message_id": self._message_id}

    async def edit_message_text(
        self,
        chat_id,
        message_id,
        text,
        *,
        reply_markup=None,
        disable_web_page_preview=True,
    ):
        self.edits.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "reply_markup": reply_markup,
            }
        )
        return True

    async def answer_callback_query(self, callback_query_id, text=None, *, show_alert=False):
        self.callbacks.append({"id": callback_query_id, "text": text, "show_alert": show_alert})
        return True

    async def send_document(self, chat_id, filename, content, *, caption=None):
        self.documents.append(
            {"chat_id": chat_id, "filename": filename, "content": content, "caption": caption}
        )
        return True


@pytest.fixture()
def bot_tables():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def fake_parse(monkeypatch):
    async def _parse(_url: str) -> ParsedProduct:
        return ParsedProduct(
            title="Bot product",
            price=1000.0,
            currency="RUB",
            in_stock=True,
            external_id="bot-1",
            shop="demo",
        )

    monkeypatch.setattr(price_service, "parse_product", _parse)
    return _parse


def message_update(text: str, *, user_id: int = 555, chat_id: int = 555) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "from": {"id": user_id, "first_name": "Test"},
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


def callback_update(
    data: str, *, user_id: int = 555, chat_id: int = 555, message_id: int = 10
) -> dict:
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cb-1",
            "from": {"id": user_id, "first_name": "Test"},
            "message": {"message_id": message_id, "chat": {"id": chat_id}},
            "data": data,
        },
    }


def add_product(
    api: FakeAPI, handlers: BotHandlers, url: str = "https://example.com/demo/shop/bot"
) -> None:
    run(handlers.handle_update(message_update(f"/add {url} 1200 10")))


def test_parse_command():
    assert parse_command("/list") == ("list", [])
    assert parse_command("/check@PricePulseBot 12") == ("check", ["12"])
    assert parse_command("hello") == ("", [])


def test_start_creates_user(bot_tables):
    api = FakeAPI()
    handlers = BotHandlers(api)

    run(handlers.handle_update(message_update("/start")))

    assert "Привет" in api.messages[0]["text"]
    buttons = api.messages[0]["reply_markup"]["inline_keyboard"]
    assert any(button.get("url") for row in buttons for button in row)
    with SessionLocal() as db:
        user = db.scalar(select(User))
        assert user is not None
        assert user.telegram_id == 555


def test_access_can_be_restricted(bot_tables, monkeypatch):
    monkeypatch.setattr(settings, "telegram_allowed_user_ids", "999")
    api = FakeAPI()
    handlers = BotHandlers(api)

    run(handlers.handle_update(message_update("/start", user_id=555)))

    assert "Доступ" in api.messages[0]["text"]
    with SessionLocal() as db:
        assert db.scalar(select(User)) is None


def test_add_list_stats_target_pause_resume_export(bot_tables, fake_parse):
    api = FakeAPI()
    handlers = BotHandlers(api)

    add_product(api, handlers)
    assert "Добавлено" in api.edits[-1]["text"]
    assert "1 000 ₽" in api.edits[-1]["text"]
    with SessionLocal() as db:
        product = db.scalar(select(Product))
        assert product is not None
        assert product.title == "Bot product"
        assert product.user.telegram_id == 555
        product_id = product.id

    run(handlers.handle_update(message_update("/list")))
    assert "Bot product" in api.messages[-1]["text"]

    run(handlers.handle_update(message_update(f"/stats {product_id}")))
    assert "Медиана 30 дней" in api.messages[-1]["text"]

    run(handlers.handle_update(message_update(f"/target {product_id} 900")))
    assert "900 ₽" in api.messages[-1]["text"]

    run(handlers.handle_update(message_update(f"/pause {product_id}")))
    assert "пауза" in api.messages[-1]["text"].lower()

    run(handlers.handle_update(message_update(f"/resume {product_id}")))
    assert "возобновлён" in api.messages[-1]["text"]

    run(handlers.handle_update(message_update(f"/export {product_id}")))
    assert api.documents
    assert api.documents[-1]["filename"].endswith(".csv")
    assert api.documents[-1]["content"].startswith(b"\xef\xbb\xbf")


def test_bare_url_is_added(bot_tables, fake_parse):
    api = FakeAPI()
    handlers = BotHandlers(api)

    run(handlers.handle_update(message_update("https://example.com/demo/shop/bare")))

    assert "Добавлено" in api.edits[-1]["text"]


def test_duplicate_and_invalid_url(bot_tables, fake_parse):
    api = FakeAPI()
    handlers = BotHandlers(api)

    add_product(api, handlers)
    add_product(api, handlers)
    assert "уже отслеживается" in api.edits[-1]["text"]

    run(handlers.handle_update(message_update("/add not-a-url")))
    assert "http://" in api.messages[-1]["text"]


def test_check_single_product(bot_tables, fake_parse, monkeypatch):
    api = FakeAPI()
    handlers = BotHandlers(api)
    add_product(api, handlers)

    async def cheaper(_url: str) -> ParsedProduct:
        return ParsedProduct(title="Bot product", price=900.0, shop="demo")

    async def allowed(_url: str):
        return True, None

    monkeypatch.setattr(price_service, "get_parser", lambda _url: SimpleNamespace(parse=cheaper))
    monkeypatch.setattr(price_service, "robots_allowed", allowed)

    run(handlers.handle_update(message_update("/check 1")))

    assert "900 ₽" in api.edits[-1]["text"]


def test_check_all(bot_tables, fake_parse, monkeypatch):
    api = FakeAPI()
    handlers = BotHandlers(api)
    add_product(api, handlers)

    async def allowed(_url: str):
        return True, None

    monkeypatch.setattr(price_service, "get_parser", lambda _url: SimpleNamespace(parse=fake_parse))
    monkeypatch.setattr(price_service, "robots_allowed", allowed)

    run(handlers.handle_update(message_update("/check all")))

    assert "Проверка завершена" in api.edits[-1]["text"]


def test_delete_confirmation_callback(bot_tables, fake_parse):
    api = FakeAPI()
    handlers = BotHandlers(api)
    add_product(api, handlers)

    run(handlers.handle_update(message_update("/delete 1")))
    assert "Удалить" in api.messages[-1]["text"]

    run(handlers.handle_update(callback_update("delok:1")))

    assert "Удалено" in api.edits[-1]["text"]
    with SessionLocal() as db:
        assert db.scalar(select(Product)) is None


def test_callback_buttons(bot_tables, fake_parse):
    api = FakeAPI()
    handlers = BotHandlers(api)
    add_product(api, handlers)

    run(handlers.handle_update(callback_update("list")))
    assert "Bot product" in api.messages[-1]["text"]

    run(handlers.handle_update(callback_update("stats:1")))
    assert "Медиана" in api.messages[-1]["text"]

    run(handlers.handle_update(callback_update("pause:1")))
    assert "пауза" in api.messages[-1]["text"].lower()

    run(handlers.handle_update(callback_update("resume:1")))
    assert "возобновлён" in api.messages[-1]["text"]
    assert api.callbacks
