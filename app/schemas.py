"""Pydantic schemas for the public API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json")
    def _serialize_datetimes(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=UTC)
            return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return value


ProductStatus = Literal["active", "paused", "error"]


class ProductCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    target_price: float | None = Field(default=None, ge=0, le=10_000_000)
    target_discount_percent: int | None = Field(default=None, ge=1, le=90)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith(("http://", "https://")):
            raise ValueError("Ссылка должна начинаться с http:// или https://")
        return value


class ProductUpdate(BaseModel):
    target_price: float | None = Field(default=None, ge=0, le=10_000_000)
    target_discount_percent: int | None = Field(default=None, ge=1, le=90)
    status: ProductStatus | None = None
    title: str | None = Field(default=None, min_length=1, max_length=512)


class ProductOut(APIModel):
    id: int
    url: str
    shop: str
    external_id: str | None
    title: str
    image_url: str | None
    currency: str
    target_price: float | None
    target_discount_percent: int | None
    status: str
    last_price: float | None
    last_checked_at: datetime | None
    last_error: str | None
    error_count: int
    created_at: datetime


class ProductCard(ProductOut):
    current_price: float | None = None
    delta_24h: float | None = None
    delta_percent_24h: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_30d: float | None = None
    discount_percent: float | None = None
    sparkline: list[float] = []
    history_points: int = 0
    below_target: bool = False
    target_progress: float | None = None
    savings_from_peak: float | None = None


class HistoryPoint(APIModel):
    checked_at: datetime
    price: float
    in_stock: bool


class PriceStats(APIModel):
    current_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_30d: float | None = None
    delta_24h: float | None = None
    delta_percent_24h: float | None = None
    change_count: int = 0
    below_target: bool = False
    savings_from_peak: float | None = None
    target_progress: float | None = None


class HistoryResponse(APIModel):
    product_id: int
    title: str
    currency: str
    points: list[HistoryPoint]
    stats: PriceStats


class NotificationOut(APIModel):
    id: int
    product_id: int
    product_title: str
    product_url: str
    shop: str
    price: float | None
    kind: str
    channel: str
    status: str
    message: str
    sent_at: datetime


class PreviewOut(APIModel):
    title: str
    price: float
    currency: str
    shop: str
    image_url: str | None
    external_id: str | None
    in_stock: bool


class CheckResult(APIModel):
    product_id: int
    title: str
    status: str
    price: float | None = None
    old_price: float | None = None
    changed: bool = False
    notifications: int = 0
    error: str | None = None
    skipped_reason: str | None = None


class CheckSummary(APIModel):
    checked: int
    changed: int
    failed: int
    skipped: int
    notifications: int
    duration_seconds: float
    results: list[CheckResult]


class DashboardSummary(APIModel):
    total_products: int
    active_products: int
    paused_products: int
    error_products: int
    below_target: int
    with_target: int
    average_discount: float | None
    checks_today: int
    notifications_sent: int
    savings_from_peak: float
    next_check_at: datetime | None
    scheduler_running: bool
    check_interval_hours: float
    telegram_configured: bool


class ShopOut(APIModel):
    id: str
    name: str
    sample_url: str | None = None
    note: str | None = None


class HealthOut(APIModel):
    status: str
    app: str
    environment: str
    database: str
    scheduler: str
    time: datetime
