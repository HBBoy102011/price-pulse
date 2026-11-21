"""Built-in demo store routes (the safest shop to parse)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from app.demo_catalog import DEMO_BY_SLUG
from app.demo_shop_pages import catalog_page, demo_robots, product_page

router = APIRouter(tags=["demo"])


@router.get("/demo/shop", response_class=HTMLResponse, include_in_schema=False)
def demo_catalog() -> str:
    return catalog_page()


@router.get("/demo/shop/{slug}", response_class=HTMLResponse, include_in_schema=False)
def demo_product(slug: str) -> str:
    product = DEMO_BY_SLUG.get(slug)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден в демо-магазине")
    return product_page(product)


@router.get("/robots.txt", response_class=PlainTextResponse, include_in_schema=False)
def robots_txt() -> str:
    return demo_robots()
