# Changelog

Все заметные изменения проекта. Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версии — [Semantic Versioning](https://semver.org/lang/ru/).

## [Unreleased]

### Планируется

- Playwright-парсеры для сайтов с клиентским рендерингом.
- Сравнение одного товара в нескольких магазинах.
- Email, web push и Discord/Slack-каналы.
- JWT-авторизация и полноценная мультипользовательность в веб-интерфейсе.

## [1.0.0] — 2026-11-22

### Added

- Добавление товара по ссылке с предпросмотром и автоопределением магазина.
- Парсеры Demo Store, Wildberries (JSON API) и Ozon (JSON-LD, best effort)
  с общим интерфейсом и реестром.
- Планировщик APScheduler: периодические проверки, защита от параллельных запусков,
  минимальный интервал между запросами.
- История цен, статистика, медиана за 30 дней, определение скидки и экономии от пика.
- Уведомления в Telegram: цель, скидка к медиане, резкое падение, ошибки парсера.
- Telegram-бот с командами `/start`, `/help`, `/list`, `/add`, `/check`, `/stats`,
  `/target`, `/pause`, `/resume`, `/delete`, `/export`, `/cancel`, `/id`.
- Привязка Telegram-аккаунта к локальному пользователю через `/start`.
- Ограничение доступа к боту по `TELEGRAM_ALLOWED_USER_IDS`.
- Дашборд: тёмная и светлая темы, Chart.js, фильтры, сортировка, поиск, модальные
  окна, лента уведомлений, тосты и CSV-экспорт.
- Встроенный Demo Store с 8 товарами и детерминированными «плавающими» ценами.
- REST API с OpenAPI/Swagger и health-check.
- SQLite локально и PostgreSQL 16 в Docker; Alembic-миграции.
- Dockerfile, docker-compose, публикация multi-arch образа в GHCR.
- CI: Python 3.11–3.13, PostgreSQL 16, `ruff`, `black`, `alembic check`.
- 45 тестов и покрытие около 80%.
- README с архитектурой, ER-диаграммой, скриншотами и инструкциями.
- Шаблоны issue/PR, CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, MIT License.

### Changed

- `telegram_id` расширен до `BIGINT`: современные Telegram ID не помещаются в 32 бита.
- Docker-образ собирается с `.dockerignore` и поддерживает переменную `$PORT` для PaaS.
- URL PostgreSQL от Render/Heroku автоматически приводится к драйверу `psycopg`.

### Fixed

- CI находил пакет `app` при запуске `pytest` из корня репозитория.
- Убран лишний bind-mount SQLite из docker-compose.

[Unreleased]: https://github.com/HBBoy102011/price-pulse/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/HBBoy102011/price-pulse/releases/tag/v1.0.0
