# PricePulse

**Трекер цен с парсерами магазинов, историей, графиками и Telegram-алертами.**

Учебный backend-проект для портфолио: парсинг сайтов, планировщик, проектирование БД с историей изменений, REST API, аккуратный веб-интерфейс и интеграция с внешним API.

[![CI](https://github.com/HBBoy102011/price-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/HBBoy102011/price-pulse/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.165-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.1-D71F00?logo=sqlalchemy&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/tests-32%20passed-c9ff4d)
![License](https://img.shields.io/badge/license-MIT-c9ff4d)

<p align="center">
  <img src="docs/screenshots/dashboard.png" alt="PricePulse — дашборд" width="100%">
</p>

---

## О проекте

PricePulse следит за товарами в интернет-магазинах: вы вставляете ссылку, сервис сам достаёт название, цену и картинку, сохраняет каждое изменение и присылает сообщение в Telegram, когда цена опускается ниже цели.

Внутри — не «скелет на один эндпоинт», а законченный сервис:

- три парсера с общим интерфейсом и graceful degradation;
- APScheduler с периодическими проверками и защитой от параллельных запусков;
- история цен и статистика (минимум, максимум, средняя, медиана за 30 дней, изменение за сутки);
- алерты по порогу цены, скидке к медиане и резкому падению;
- SQLite локально и PostgreSQL в Docker без изменения кода;
- Alembic-миграции, 32 теста, ruff + black, GitHub Actions;
- собственный дашборд без сборщика: тёмная/светлая тема, графики Chart.js, поиск, фильтры, модальные окна и CSV-экспорт.

### Почему это интересно смотреть

| Что показано | Где смотреть |
|---|---|
| Парсинг HTML и JSON API | `app/parsers/` |
| Устойчивость к ошибкам и антиботу | `app/services/price_service.py` |
| Планировщик и фоновые задачи | `app/scheduler.py` |
| БД с историей и каскадами | `app/models/models.py` |
| REST API и валидация | `app/api/`, `app/schemas.py` |
| Визуализация и UX | `web/` |
| Тесты, миграции, Docker, CI | `tests/`, `migrations/`, `Dockerfile`, `.github/` |

---

## Возможности

### Товары и цены

- Добавление товара по ссылке с предпросмотром **до** сохранения.
- Автоматическое определение магазина, названия, цены, валюты и изображения.
- История цен: каждое изменение — отдельная запись.
- Статистика: минимум, максимум, средняя, медиана 30 дней, изменение за 24 часа, число изменений, экономия от исторического пика.
- Пауза и возобновление отслеживания, редактирование порога, удаление вместе с историей.
- Ручная проверка одного товара или всех сразу.
- Экспорт истории в CSV (`;`, UTF-8 BOM — открывается в Excel).

### Уведомления

- 🎯 **Цель достигнута** — цена опустилась до заданного порога.
- 🔥 **Настоящая скидка** — цена ниже медианы за 30 дней на заданный процент.
- 📉 **Резкое падение** — цена упала более чем на 8% за одну проверку.
- ⚠️ **Ошибка парсера** — товар не проверяется после 3 неудач подряд.
- Все события сохраняются в ленту. Если Telegram не настроен, они получают статус `skipped` — демо-режим виден прямо в интерфейсе.
- Кулдауны: цель и падение — раз в 24 часа, скидка — раз в 7 дней, ошибка — раз в 24 часа.

### Дашборд

- Тёмная glassmorphism-тема и светлая тема с сохранением выбора.
- Живые метрики: товары, цели, средняя скидка, проверки за день.
- Карточки со sparkline, прогрессом до цели и статусом.
- График цены за 7 / 30 / 90 дней или год, линия цели, тултипы, статистика за выбранный период.
- Поиск, фильтры по статусу, сортировка, скелетоны загрузки и пустые состояния.
- Лента уведомлений, тосты, горячие клавиши (`/` — поиск, `Esc` — закрыть).
- Полностью адаптивная вёрстка, шрифты Manrope и Unbounded хостятся локально.

### Встроенный Demo Store

Чтобы проект можно было запустить и показать без внешней сети, внутри приложения живёт демо-магазин:

- 8 товаров с SVG-иллюстрациями и карточками товара;
- детерминированные «плавающие» цены — история всегда выглядит живой;
- страницы размечены атрибутами `data-product-*`, которые читает парсер;
- собственный `robots.txt`.

---

## Скриншоты

### График цены

<p align="center">
  <img src="docs/screenshots/chart.png" alt="График цены за 30 дней" width="100%">
</p>

### Добавление товара с предпросмотром

<p align="center">
  <img src="docs/screenshots/add-product.png" alt="Добавление товара" width="100%">
</p>

### Лента уведомлений

<p align="center">
  <img src="docs/screenshots/notifications.png" alt="Лента уведомлений" width="100%">
</p>

### Demo Store

<p align="center">
  <img src="docs/screenshots/demo-store.png" alt="Demo Store" width="100%">
</p>

### Светлая тема

<p align="center">
  <img src="docs/screenshots/light-theme.png" alt="Светлая тема" width="100%">
</p>

<details>
<summary>Swagger UI</summary>

<p align="center">
  <img src="docs/screenshots/api-docs.png" alt="Swagger UI" width="100%">
</p>

</details>

---

## Технологии

| Слой | Технология | Зачем |
|---|---|---|
| Язык | Python 3.11+ | Современный синтаксис, `asyncio` |
| API | FastAPI + Pydantic 2 | Валидация, OpenAPI, async |
| ORM | SQLAlchemy 2 + Alembic | Модели, миграции |
| БД | SQLite → PostgreSQL | Старт без зависимостей, прод — Postgres |
| Парсинг | httpx + BeautifulSoup4 | HTML и JSON API |
| Планировщик | APScheduler | Периодические проверки |
| Графики | Chart.js 4 | Без сборщика и CDN |
| Уведомления | Telegram Bot API | Внешняя интеграция |
| Тесты | pytest | 32 теста |
| Качество | ruff + black | Линт и форматирование |
| Деплой | Docker, docker-compose | Локально и на VPS |

---

## Архитектура

```mermaid
flowchart LR
    U[Браузер] -->|HTML + JS| W[FastAPI]
    W --> API[REST API]
    API --> S[PriceService]
    S --> P[Парсеры]
    P --> D[Demo Store]
    P --> WB[Wildberries JSON API]
    P --> OZ[Ozon JSON-LD]
    S --> DB[(SQLite / PostgreSQL)]
    S --> N[Notifier]
    N --> TG[Telegram Bot API]
    SCH[APScheduler] -->|каждые 6 часов| S
    R[robots.txt] -->|проверка| P
```

**Как проходит проверка:**

1. Планировщик запускает `check_all()` и берёт активные товары.
2. Для каждого товара проверяется `robots.txt` и минимальный интервал между запросами.
3. Парсер магазина возвращает нормализованный `ParsedProduct`.
4. Если цена изменилась — в `price_history` добавляется запись.
5. `PriceService` проверяет цель, скидку к медиане и падение, создаёт уведомления.
6. Уведомление сохраняется в БД и отправляется в Telegram (или остаётся в демо-режиме).
7. Ошибка увеличивает `error_count`; после порога товар получает статус `error`, а при успехе счётчик сбрасывается.

---

## Модель данных

```mermaid
erDiagram
    USERS ||--o{ PRODUCTS : owns
    PRODUCTS ||--o{ PRICE_HISTORY : has
    PRODUCTS ||--o{ NOTIFICATIONS : triggers

    USERS {
        int id PK
        int telegram_id UK
        string display_name
        datetime created_at
    }

    PRODUCTS {
        int id PK
        int user_id FK
        text url
        string shop
        string external_id
        string title
        text image_url
        string currency
        numeric target_price
        int target_discount_percent
        string status
        numeric last_price
        datetime last_checked_at
        text last_error
        int error_count
        datetime created_at
        datetime updated_at
    }

    PRICE_HISTORY {
        int id PK
        int product_id FK
        numeric price
        string currency
        bool in_stock
        datetime checked_at
    }

    NOTIFICATIONS {
        int id PK
        int product_id FK
        numeric price
        string kind
        string channel
        string status
        text message
        datetime sent_at
    }
```

Ключевые решения:

- `UNIQUE(user_id, url)` защищает от дублей на уровне БД.
- История и уведомления удаляются каскадом вместе с товаром.
- Индексы `(product_id, checked_at)` и `(product_id, sent_at)` ускоряют графики и ленту.
- Деньги хранятся в `Numeric(12, 2)`, а не в `float`.

---

## Быстрый старт

### 1. Клонирование и зависимости

```bash
git clone https://github.com/HBBoy102011/price-pulse.git
cd price-pulse

python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
```

### 2. Конфигурация

```bash
cp .env.example .env
```

Для локального запуска менять ничего не нужно: используется SQLite и демо-режим Telegram.

### 3. Демо-данные (опционально, но красиво)

```bash
python -m scripts.seed_demo
```

Скрипт создаёт 8 товаров и 90 дней истории — дашборд сразу выглядит живым.

### 4. Запуск

```bash
uvicorn app.main:app --reload
```

| Адрес | Что там |
|---|---|
| http://localhost:8000 | Дашборд |
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/demo/shop | Demo Store |
| http://localhost:8000/api/health | Health check |

> Миграции: локально таблицы создаются автоматически (`AUTO_CREATE_TABLES=true`). Для продакшена выполните `alembic upgrade head` и выставьте `AUTO_CREATE_TABLES=false`.

---

## Docker

В репозитории есть `Dockerfile` и `docker-compose.yml` с PostgreSQL.

```bash
docker compose up --build
```

- приложение: http://localhost:8000
- PostgreSQL: внутренний сервис `db`, данные в volume `pgdata`
- миграции применяются автоматически перед стартом (`alembic upgrade head`)

Заполнить демо-данными:

```bash
docker compose exec app python -m scripts.seed_demo
```

Остановить и удалить данные:

```bash
docker compose down -v
```

---

## Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather): `/newbot` → получите токен.
2. Узнайте `chat_id`: напишите боту сообщение и откройте
   `https://api.telegram.org/bot<TOKEN>/getUpdates`, либо используйте [@userinfobot](https://t.me/userinfobot).
3. Заполните `.env`:

```env
TELEGRAM_BOT_TOKEN=123456:AA...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_ENABLED=true
```

4. Перезапустите приложение.

Без токена сервис работает в **демо-режиме**: уведомления создаются, сохраняются в ленте и помечаются как `skipped`. Это позволяет показывать весь сценарий без внешних секретов.

---

## REST API

Полная интерактивная документация — `/docs`.

| Метод | Эндпоинт | Описание |
|---|---|---|
| `GET` | `/api/health` | Статус приложения, БД и планировщика |
| `GET` | `/api/summary` | Сводка для дашборда |
| `GET` | `/api/shops` | Поддерживаемые магазины |
| `GET` | `/api/products` | Список товаров (`status`, `shop`, `q`, `sort`) |
| `POST` | `/api/products` | Добавить товар по ссылке |
| `POST` | `/api/preview` | Разобрать ссылку без сохранения |
| `GET` | `/api/products/{id}` | Карточка товара |
| `PATCH` | `/api/products/{id}` | Изменить цель, скидку, статус, название |
| `DELETE` | `/api/products/{id}` | Удалить товар и историю |
| `POST` | `/api/products/{id}/check` | Проверить один товар (`?force=true`) |
| `GET` | `/api/products/{id}/history` | История (`days`, `limit`) |
| `GET` | `/api/products/{id}/stats` | Статистика |
| `GET` | `/api/products/{id}/history.csv` | CSV-экспорт |
| `GET` | `/api/products/{id}/notifications` | Уведомления товара |
| `POST` | `/api/check` | Проверить все активные товары |
| `GET` | `/api/notifications` | Лента событий (`limit`, `kind`, `status`) |

### Примеры

Добавить товар:

```bash
curl -X POST http://localhost:8000/api/products \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://localhost:8000/demo/shop/aurora-headphones",
    "target_price": 22000,
    "target_discount_percent": 10
  }'
```

Предпросмотр без сохранения:

```bash
curl -X POST http://localhost:8000/api/preview \
  -H "Content-Type: application/json" \
  -d '{"url": "http://localhost:8000/demo/shop/nova-watch"}'
```

Запустить проверку вручную:

```bash
curl -X POST http://localhost:8000/api/check \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

Скачать историю:

```bash
curl -OJ http://localhost:8000/api/products/1/history.csv
```

---

## Парсеры и этика

| Магазин | Способ | Статус |
|---|---|---|
| **Demo Store** | HTML, атрибуты `data-product-*` | Работает офлайн, используется в тестах |
| **Wildberries** | Публичный JSON API карточки товара | Основной «реальный» парсер |
| **Ozon** | JSON-LD + резервный разбор HTML | Best effort: Ozon может включить антибот |

Общий интерфейс:

```python
class BaseParser(ABC):
    def can_handle(self, url: str) -> bool: ...
    async def parse(self, url: str) -> ParsedProduct: ...
```

Добавить новый магазин = создать класс-наследник и зарегистрировать его в `app/parsers/registry.py`.

### Принципы

- **robots.txt** проверяется перед запросом и кешируется на 6 часов.
- **Честный User-Agent**: `PricePulseBot/1.0 (+ссылка на репозиторий)`.
- **Пауза между запросами** (`REQUEST_DELAY_SECONDS=0.4`).
- **Минимальный интервал** между проверками одного товара — 30 минут.
- Нет обхода авторизации, капчи и платных API.
- Проект **учебный**: не используйте его для коммерческого скрейпинга и уважайте условия площадок.

---

## Тесты и качество кода

```bash
pytest -q
ruff check .
black --check .
```

Покрыто:

- нормализация цен (`12 990,50 ₽`, `$1,299.00`, `1.299,00 €`);
- парсинг Demo Store, Wildberries JSON и Ozon JSON-LD на сохранённых фикстурах;
- CRUD, предпросмотр, история, CSV, ручная проверка;
- уведомления о цели, скидке, падении и ошибке;
- порог из 3 ошибок и сброс счётчика при успехе;
- rate-limit: повторная проверка слишком рано возвращает `skipped`;
- health-check и сводка дашборда.

С покрытием:

```bash
pytest --cov=app --cov-report=term-missing
```

CI прогоняет линтер, форматтер и тесты на Python 3.11, 3.12 и 3.13.

---

## Структура проекта

```text
price-pulse/
├── app/
│   ├── api/                 # products, checks, dashboard, demo
│   ├── models/              # SQLAlchemy-модели
│   ├── parsers/             # base, demo, wildberries, ozon, registry
│   ├── services/            # price_service, notifier, robots, stats
│   ├── config.py            # настройки из .env
│   ├── database.py          # engine, session, init_db
│   ├── demo_catalog.py      # каталог Demo Store
│   ├── demo_shop_pages.py   # HTML витрины
│   ├── main.py              # FastAPI-приложение
│   ├── scheduler.py         # APScheduler
│   └── schemas.py           # Pydantic-схемы
├── migrations/              # Alembic
├── scripts/
│   ├── seed_demo.py         # демо-данные
│   └── capture_screenshots.py
├── tests/                   # pytest + фикстуры
├── web/                     # дашборд: HTML, CSS, JS, шрифты, Chart.js
├── docs/screenshots/        # скриншоты для README
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .github/workflows/ci.yml
```

---

## Roadmap

- [x] MVP: добавление по ссылке, 3 парсера, история, график, Telegram
- [x] Скидка к медиане и обнаружение резких падений
- [x] CSV-экспорт, пауза, ручная проверка
- [x] Alembic, Docker, CI, 32 теста
- [ ] Playwright для сайтов, которые рендерят цену на клиенте
- [ ] Сравнение одного товара в нескольких магазинах
- [ ] Пользовательские аккаунты и авторизация
- [ ] Celery + Redis для горизонтального масштабирования
- [ ] Web Push и email-дубли уведомлений
- [ ] Деплой на Render / Railway / VPS

---

## Лицензия

[MIT](LICENSE) © 2026 HBBoy102011

Проект создан в учебных целях. Парсите бережно: `robots.txt`, лимиты и честный User-Agent уже встроены.
