"""Product CRUD, price history and manual checks."""

from __future__ import annotations

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import PRODUCT_ACTIVE, Notification, Product
from app.parsers import ParserError, parse_product, supported_shops
from app.schemas import (
    CheckResult,
    HistoryPoint,
    HistoryResponse,
    PreviewOut,
    PriceStats,
    ProductCard,
    ProductCreate,
    ProductUpdate,
)
from app.services.price_service import (
    DuplicateProductError,
    check_product,
    create_product,
)
from app.services.stats import (
    as_utc,
    build_stats,
    card_payload,
    get_history,
    to_float,
)

router = APIRouter(prefix="/api", tags=["products"])
DbSession = Annotated[Session, Depends(get_db)]


def _get_product(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


@router.get("/shops")
def list_shops() -> list[dict]:
    return supported_shops()


@router.get("/products", response_model=list[ProductCard])
def list_products(
    db: DbSession,
    status_filter: Literal["active", "paused", "error"] | None = Query(None, alias="status"),
    shop: str | None = None,
    q: str | None = None,
    sort: Literal["recent", "price_asc", "price_desc", "discount", "title"] = "recent",
) -> list[dict]:
    query = select(Product)
    if status_filter:
        query = query.where(Product.status == status_filter)
    if shop:
        query = query.where(Product.shop == shop)
    if q:
        query = query.where(Product.title.ilike(f"%{q.strip()}%"))
    products = list(db.scalars(query).all())

    payloads = [card_payload(db, product) for product in products]

    if sort == "price_asc":
        payloads.sort(key=lambda item: item["current_price"] or float("inf"))
    elif sort == "price_desc":
        payloads.sort(key=lambda item: item["current_price"] or 0, reverse=True)
    elif sort == "discount":
        payloads.sort(key=lambda item: item["discount_percent"] or -999, reverse=True)
    elif sort == "title":
        payloads.sort(key=lambda item: item["title"].lower())
    else:
        payloads.sort(
            key=lambda item: as_utc(item["last_checked_at"]) or as_utc(item["created_at"]),
            reverse=True,
        )
    return payloads


@router.post("/products", response_model=ProductCard, status_code=status.HTTP_201_CREATED)
async def add_product(payload: ProductCreate, db: DbSession) -> dict:
    try:
        product = await create_product(db, payload)
    except DuplicateProductError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return card_payload(db, product)


@router.post("/preview", response_model=PreviewOut)
async def preview_product(payload: ProductCreate) -> PreviewOut:
    """Parse a link without saving it — used by the add-product form."""
    try:
        parsed = await parse_product(payload.url)
    except ParserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PreviewOut(
        title=parsed.title,
        price=parsed.price,
        currency=parsed.currency,
        shop=parsed.shop,
        image_url=parsed.image_url,
        external_id=parsed.external_id,
        in_stock=parsed.in_stock,
    )


@router.get("/products/{product_id}", response_model=ProductCard)
def get_product(product_id: int, db: DbSession) -> dict:
    return card_payload(db, _get_product(db, product_id))


@router.patch("/products/{product_id}", response_model=ProductCard)
def update_product(product_id: int, payload: ProductUpdate, db: DbSession) -> dict:
    product = _get_product(db, product_id)
    fields = payload.model_fields_set

    if "target_price" in fields:
        product.target_price = (
            None if payload.target_price is None else round(payload.target_price, 2)
        )
    if "target_discount_percent" in fields:
        product.target_discount_percent = payload.target_discount_percent
    if "title" in fields and payload.title:
        product.title = payload.title.strip()
    if "status" in fields and payload.status:
        product.status = payload.status
        if payload.status == PRODUCT_ACTIVE:
            product.error_count = 0
            product.last_error = None

    db.commit()
    db.refresh(product)
    return card_payload(db, product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: DbSession) -> Response:
    product = _get_product(db, product_id)
    db.delete(product)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/products/{product_id}/check", response_model=CheckResult)
async def check_single_product(
    product_id: int,
    db: DbSession,
    force: bool = Query(True, description="Игнорировать минимальный интервал между проверками"),
) -> CheckResult:
    product = _get_product(db, product_id)
    if product.status == "paused" and not force:
        raise HTTPException(status_code=409, detail="Товар на паузе")
    return await check_product(db, product, force=force)


@router.get("/products/{product_id}/history", response_model=HistoryResponse)
def product_history(
    product_id: int,
    db: DbSession,
    days: int = Query(90, ge=1, le=3650),
    limit: int = Query(500, ge=2, le=5000),
) -> HistoryResponse:
    product = _get_product(db, product_id)
    rows = get_history(db, product.id, days=days, limit=limit)
    stats = build_stats(db, product, days=days)
    return HistoryResponse(
        product_id=product.id,
        title=product.title,
        currency=product.currency,
        points=[
            HistoryPoint(
                checked_at=as_utc(row.checked_at),
                price=round(float(row.price), 2),
                in_stock=row.in_stock,
            )
            for row in rows
        ],
        stats=PriceStats(**stats),
    )


@router.get("/products/{product_id}/stats", response_model=PriceStats)
def product_stats(product_id: int, db: DbSession) -> PriceStats:
    product = _get_product(db, product_id)
    return PriceStats(**build_stats(db, product))


@router.get("/products/{product_id}/history.csv")
def export_history(product_id: int, db: DbSession, days: int = Query(365, ge=1, le=3650)):
    product = _get_product(db, product_id)
    rows = get_history(db, product.id, days=days)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["checked_at", "price", "currency", "in_stock"])
    for row in rows:
        writer.writerow(
            [
                as_utc(row.checked_at).isoformat() if row.checked_at else "",
                f"{float(row.price):.2f}",
                row.currency,
                "true" if row.in_stock else "false",
            ]
        )
    content = "\ufeff" + buffer.getvalue()
    filename = f"pricepulse-product-{product.id}-history.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/products/{product_id}/notifications")
def product_notifications(product_id: int, db: DbSession):
    _get_product(db, product_id)
    rows = list(
        db.scalars(
            select(Notification)
            .where(Notification.product_id == product_id)
            .order_by(Notification.sent_at.desc())
            .limit(50)
        ).all()
    )
    return [
        {
            "id": row.id,
            "kind": row.kind,
            "price": to_float(row.price),
            "status": row.status,
            "message": row.message,
            "sent_at": as_utc(row.sent_at),
        }
        for row in rows
    ]
