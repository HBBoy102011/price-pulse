"""Tiny async client for the Telegram Bot API.

Only the handful of methods PricePulse needs are wrapped here. Keeping the
surface small makes the bot easy to test with a fake client and avoids pulling
a full framework into the project.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TelegramAPIError(RuntimeError):
    """Raised when Telegram returns ``ok: false`` or the request fails."""

    def __init__(self, method: str, description: str, status_code: int | None = None):
        self.method = method
        self.description = description
        self.status_code = status_code
        super().__init__(f"{method}: {description}")


class TelegramAPI:
    def __init__(
        self,
        token: str,
        *,
        base_url: str = "https://api.telegram.org",
        timeout: float = 45.0,
    ) -> None:
        self._base = f"{base_url.rstrip('/')}/bot{token}"
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10.0))

    async def close(self) -> None:
        await self._client.aclose()

    async def call(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        try:
            if files is not None:
                response = await self._client.post(
                    f"{self._base}/{method}", data=data or {}, files=files
                )
            else:
                response = await self._client.post(f"{self._base}/{method}", json=params or {})
        except httpx.HTTPError as exc:
            raise TelegramAPIError(method, str(exc)) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TelegramAPIError(
                method, f"HTTP {response.status_code}: {response.text[:200]}", response.status_code
            ) from exc

        if not payload.get("ok"):
            raise TelegramAPIError(
                method,
                str(payload.get("description") or "unknown Telegram error"),
                response.status_code,
            )
        return payload.get("result")

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe")

    async def get_updates(self, offset: int, timeout: int = 25) -> list[dict[str, Any]]:
        result = await self.call(
            "getUpdates",
            params={
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message", "callback_query"],
            },
        )
        return list(result or [])

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        disable_web_page_preview: bool = True,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self.call("sendMessage", params=params)

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        disable_web_page_preview: bool = True,
    ) -> Any:
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_web_page_preview,
        }
        if reply_markup is not None:
            params["reply_markup"] = reply_markup
        return await self.call("editMessageText", params=params)

    async def answer_callback_query(
        self, callback_query_id: str, text: str | None = None, *, show_alert: bool = False
    ) -> Any:
        params: dict[str, Any] = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }
        if text:
            params["text"] = text[:200]
        return await self.call("answerCallbackQuery", params=params)

    async def send_document(
        self,
        chat_id: int | str,
        filename: str,
        content: bytes,
        *,
        caption: str | None = None,
    ) -> Any:
        data: dict[str, Any] = {"chat_id": str(chat_id), "parse_mode": "HTML"}
        if caption:
            data["caption"] = caption[:1024]
        files = {"document": (filename, content, "text/csv")}
        return await self.call("sendDocument", data=data, files=files)
