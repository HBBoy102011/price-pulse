"""CSV export shared by the REST API and the Telegram bot."""

from __future__ import annotations

import csv
import io

from app.models.models import PriceHistory, Product
from app.services.stats import as_utc


def build_history_csv(product: Product, rows: list[PriceHistory]) -> tuple[str, bytes]:
    """Return ``(filename, content)`` with a UTF-8 BOM for Excel."""
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
    content = ("\ufeff" + buffer.getvalue()).encode("utf-8")
    return f"pricepulse-product-{product.id}-history.csv", content
