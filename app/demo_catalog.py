"""Catalogue of the built-in demo store."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class DemoProduct:
    slug: str
    title: str
    brand: str
    category: str
    base_price: int
    description: str
    rating: float
    reviews: int
    badge: str
    image: str
    specs: dict[str, str] = field(default_factory=dict)


DEMO_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct(
        slug="aurora-headphones",
        title="Aurora Studio ANC",
        brand="Aurora",
        category="Наушники",
        base_price=24_990,
        description=(
            "Полноразмерные беспроводные наушники с гибридным шумоподавлением, "
            "40-мм драйверами и 38 часами автономности. Мягкие амбушюры из "
            "протеиновой кожи и складная конструкция для поездок."
        ),
        rating=4.8,
        reviews=1_284,
        badge="Хит",
        image="/static/img/products/aurora-headphones.svg",
        specs={
            "Тип": "Накладные, беспроводные",
            "Автономность": "до 38 часов",
            "Шумоподавление": "Гибридное ANC",
            "Подключение": "Bluetooth 5.3, USB-C",
            "Вес": "268 г",
        },
    ),
    DemoProduct(
        slug="nova-watch",
        title="Nova Watch S2",
        brand="Nova",
        category="Смарт-часы",
        base_price=18_490,
        description=(
            "Смарт-часы с AMOLED-экраном 1.43″, GPS, пульсометром и анализом "
            "сна. Корпус из авиационного алюминия, защита 5 ATM и до 14 дней "
            "работы без подзарядки."
        ),
        rating=4.7,
        reviews=842,
        badge="Новинка",
        image="/static/img/products/nova-watch.svg",
        specs={
            "Экран": "1.43″ AMOLED, 466×466",
            "Защита": "5 ATM",
            "Датчики": "GPS, пульс, SpO₂",
            "Автономность": "до 14 дней",
            "Совместимость": "iOS 15+, Android 10+",
        },
    ),
    DemoProduct(
        slug="pulse-keyboard",
        title="Pulse K75 Mechanical",
        brand="Pulse",
        category="Клавиатуры",
        base_price=12_990,
        description=(
            "Механическая клавиатура формата 75% с горячей заменой свитчей, "
            "гаскет-маунтом и тройным подключением. Алюминиевый корпус, "
            "PBT-кейкапы и настраиваемая RGB-подсветка."
        ),
        rating=4.9,
        reviews=517,
        badge="Выбор редакции",
        image="/static/img/products/pulse-keyboard.svg",
        specs={
            "Формат": "75%",
            "Свитчи": "Linear, hot-swap",
            "Подключение": "USB-C, Bluetooth, 2.4 ГГц",
            "Кейкапы": "PBT double-shot",
            "Батарея": "4000 мА·ч",
        },
    ),
    DemoProduct(
        slug="drift-sneakers",
        title="Drift Runner V3",
        brand="Drift",
        category="Кроссовки",
        base_price=9_490,
        description=(
            "Беговые кроссовки с пеной двойной плотности и дышащим верхом из "
            "инженерного текстиля. Подходят для ежедневных тренировок и "
            "длинных прогулок."
        ),
        rating=4.6,
        reviews=2_031,
        badge="−20%",
        image="/static/img/products/drift-sneakers.svg",
        specs={
            "Назначение": "Бег, повседневная носка",
            "Подошва": "EVA двойной плотности",
            "Верх": "Инженерный текстиль",
            "Вес": "245 г (42 EU)",
            "Размеры": "36–46 EU",
        },
    ),
    DemoProduct(
        slug="brew-coffee",
        title="Brew Master Pro",
        brand="Brew",
        category="Кофемашины",
        base_price=54_900,
        description=(
            "Зерновая кофемашина с керамической кофемолкой, автоматическим "
            "вспениванием молока и 12 предустановленными рецептами. Управление "
            "со смартфона и съёмный резервуар на 2 литра."
        ),
        rating=4.8,
        reviews=396,
        badge="Топ продаж",
        image="/static/img/products/brew-coffee.svg",
        specs={
            "Тип": "Зерновая, автоматическая",
            "Давление": "19 бар",
            "Кофемолка": "Керамическая, 12 степеней",
            "Резервуар": "2 л",
            "Рецепты": "12 программ",
        },
    ),
    DemoProduct(
        slug="nomad-backpack",
        title="Nomad 28L",
        brand="Nomad",
        category="Рюкзаки",
        base_price=7_990,
        description=(
            "Городской рюкзак на 28 литров с отделением для ноутбука 16″, "
            "водоотталкивающей тканью и скрытым карманом для документов. "
            "Продуманная эргономика для ежедневных поездок."
        ),
        rating=4.5,
        reviews=689,
        badge="Эко",
        image="/static/img/products/nomad-backpack.svg",
        specs={
            "Объём": "28 л",
            "Ноутбук": "до 16″",
            "Ткань": "Recycled 600D",
            "Вес": "980 г",
            "Гарантия": "3 года",
        },
    ),
    DemoProduct(
        slug="halo-lamp",
        title="Halo Desk Light",
        brand="Halo",
        category="Освещение",
        base_price=6_490,
        description=(
            "Настольная лампа с регулировкой температуры 2700–6500K, "
            "беспроводной зарядкой в основании и датчиком освещённости. "
            "Матовый алюминий и минималистичный силуэт."
        ),
        rating=4.7,
        reviews=421,
        badge="Дизайн",
        image="/static/img/products/halo-lamp.svg",
        specs={
            "Цветовая температура": "2700–6500 K",
            "Яркость": "до 1000 лм",
            "Зарядка": "Qi 15 Вт",
            "Материал": "Алюминий",
            "Питание": "USB-C",
        },
    ),
    DemoProduct(
        slug="echo-speaker",
        title="Echo Mini",
        brand="Echo",
        category="Акустика",
        base_price=8_990,
        description=(
            "Портативная колонка с 360° звуком, пассивным сабвуфером и "
            "защитой IP67. До 20 часов работы, стереопара из двух колонок и "
            "быстрая зарядка за 45 минут."
        ),
        rating=4.6,
        reviews=1_102,
        badge="IP67",
        image="/static/img/products/echo-speaker.svg",
        specs={
            "Мощность": "2×20 Вт",
            "Защита": "IP67",
            "Автономность": "до 20 часов",
            "Bluetooth": "5.3",
            "Зарядка": "USB-C, 45 мин",
        },
    ),
)

DEMO_BY_SLUG: dict[str, DemoProduct] = {product.slug: product for product in DEMO_PRODUCTS}


def demo_price(base_price: float, slug: str, at: datetime | None = None) -> float:
    """Deterministic, gently drifting price so the demo always has movement."""
    moment = at or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    days = moment.timestamp() / 86_400
    phase = sum(ord(char) for char in slug) % 97

    long_wave = 0.055 * math.sin(days / 14 * 2 * math.pi + phase)
    short_wave = 0.018 * math.sin(days / 3 * 2 * math.pi + phase * 1.7)
    promo_cycle = (int(days) + phase) % 29
    promo = -0.07 if promo_cycle == 0 else (-0.03 if promo_cycle in (11, 12) else 0.0)

    price = base_price * (1 + long_wave + short_wave + promo)
    return float(max(99, round(price / 10) * 10 - 1))
