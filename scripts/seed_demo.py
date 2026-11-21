"""Seed the database with a beautiful, realistic demo dataset.

Usage:
    python -m scripts.seed_demo
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

from app.config import settings
from app.database import SessionLocal, init_db
from app.demo_catalog import DEMO_PRODUCTS, demo_price
from app.models.models import Notification, PriceHistory, Product, User, utcnow
from app.services.notifier import build_message
from sqlalchemy import delete

TARGETS = {
    "aurora-headphones": 23_500,
    "nova-watch": 18_990,
    "pulse-keyboard": 13_990,
    "drift-sneakers": 8_990,
    "brew-coffee": 55_900,
    "nomad-backpack": 7_990,
    "halo-lamp": 5_990,
    "echo-speaker": 8_490,
}
DISCOUNT_TARGETS = {
    "aurora-headphones": 12,
    "pulse-keyboard": 15,
    "brew-coffee": 10,
}
PAUSED = {"halo-lamp"}

random.seed(42)


def reset(db) -> None:
    db.execute(delete(Notification))
    db.execute(delete(PriceHistory))
    db.execute(delete(Product))
    db.execute(delete(User))
    db.commit()


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        reset(db)
        user = User(display_name="PricePulse demo", telegram_id=settings.default_user_telegram_id)
        db.add(user)
        db.commit()
        db.refresh(user)

        now = utcnow()
        products: dict[str, Product] = {}

        for demo in DEMO_PRODUCTS:
            current_price = demo_price(demo.base_price, demo.slug, now)
            product = Product(
                user_id=user.id,
                url=f"{settings.public_base_url.rstrip('/')}/demo/shop/{demo.slug}",
                shop="demo",
                external_id=demo.slug,
                title=demo.title,
                image_url=demo.image,
                currency="RUB",
                target_price=Decimal(str(TARGETS[demo.slug])),
                target_discount_percent=DISCOUNT_TARGETS.get(demo.slug),
                status="paused" if demo.slug in PAUSED else "active",
                last_price=Decimal(str(current_price)),
                last_checked_at=now - timedelta(minutes=random.randint(3, 110)),
            )
            db.add(product)
            db.flush()
            products[demo.slug] = product

            # 90 days of history, two points per day.
            points = []
            for step in range(180, -1, -1):
                moment = now - timedelta(hours=12 * step)
                price = demo_price(demo.base_price, demo.slug, moment)
                points.append(
                    PriceHistory(
                        product_id=product.id,
                        price=Decimal(str(price)),
                        currency="RUB",
                        in_stock=True,
                        checked_at=moment,
                    )
                )
            db.add_all(points)

        db.commit()

        # A few realistic events for the notification feed.
        events = [
            ("aurora-headphones", "target", 2, 4, "Цель 23 500 ₽ достигнута — сейчас дешевле"),
            ("pulse-keyboard", "discount", 4, 11, "Скидка 16% к медиане за 30 дней"),
            ("drift-sneakers", "price_drop", 1, 7, "Цена упала на 9% за одну проверку"),
            ("brew-coffee", "target", 9, 18, "Цена впервые опустилась ниже цели"),
            ("echo-speaker", "price_drop", 0, 3, "Цена снизилась на 8%"),
        ]
        for slug, kind, days_ago, hours_ago, extra in events:
            product = products[slug]
            sent_at = now - timedelta(days=days_ago, hours=hours_ago)
            notification = Notification(
                product_id=product.id,
                price=product.last_price,
                kind=kind,
                channel="telegram",
                status="skipped",
                message=build_message(product, kind, product.last_price, extra),
                sent_at=sent_at,
            )
            db.add(notification)

        db.commit()

        total_history = sum(
            db.query(PriceHistory).filter(PriceHistory.product_id == product.id).count()
            for product in products.values()
        )
        print(f"Seeded {len(products)} products, {total_history} price points.")
        print(f"Open {settings.public_base_url} and enjoy.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
