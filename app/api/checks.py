"""Manual check endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CheckSummary
from app.services.price_service import check_all

router = APIRouter(prefix="/api", tags=["checks"])
DbSession = Annotated[Session, Depends(get_db)]


class CheckRequest(BaseModel):
    product_ids: list[int] | None = Field(default=None, max_length=200)
    force: bool = True


@router.post("/check", response_model=CheckSummary)
async def run_check(db: DbSession, payload: CheckRequest | None = None) -> CheckSummary:
    """Run a check cycle immediately (handy for demos and debugging)."""
    request = payload or CheckRequest()
    return await check_all(db, force=request.force, product_ids=request.product_ids)
