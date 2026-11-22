# Contributing to PricePulse

Спасибо, что заглянули! Проект учебный, но код и процессы здесь как в небольшом
продакшене: типы, тесты, миграции, линтеры и ревью. Любая помощь приветствуется —
от опечатки в README до нового парсера.

## С чего начать

1. Проверьте [Issues](https://github.com/HBBoy102011/price-pulse/issues): возможно,
   задача уже описана.
2. Для крупных изменений сначала создайте issue или обсуждение — так мы не потратим
   время на разную реализацию одного и того же.
3. Мелкие исправления (typo, документация, тест) можно присылать сразу Pull Request.

## Локальное окружение

```bash
git clone https://github.com/HBBoy102011/price-pulse.git
cd price-pulse

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
cp .env.example .env
python -m scripts.seed_demo
uvicorn app.main:app --reload
```

Приложение: <http://localhost:8000>, документация API: <http://localhost:8000/docs>.

### Docker

```bash
docker compose up --build -d
docker compose exec app python -m scripts.seed_demo
```

## Проверки перед PR

```bash
pytest -q
ruff check .
black --check .
alembic check
```

Все четыре команды должны проходить. CI дополнительно прогоняет тесты на
Python 3.11–3.13 и на PostgreSQL 16.

### Полезные команды

```bash
pytest -q --cov=app --cov-report=term-missing
ruff check . --fix
black .
alembic revision -m "short description"
alembic upgrade head
```

## Стиль кода

- Python 3.11+, современные аннотации типов (`list[str]`, `X | None`).
- Код, имена и комментарии — на английском; пользовательские строки и README — на русском.
- Строки до 100 символов, форматирование только через `black`.
- Бизнес-логика живёт в `app/services/`, HTTP-слой — в `app/api/`, парсеры — в `app/parsers/`.
- Деньги храним в `Decimal`/`Numeric`, не во `float`.
- Новые внешние запросы — только через `httpx` с таймаутом и понятным User-Agent.
- Секреты и токены — только в `.env`; в репозиторий они не попадают.

## Как добавить парсер

1. Создайте класс-наследник `BaseParser` в `app/parsers/<shop>.py`.
2. Реализуйте `can_handle(url)` и `async parse(url) -> ParsedProduct`.
3. Зарегистрируйте парсер в `app/parsers/registry.py`.
4. Добавьте фикстуру с сохранённым HTML/JSON в `tests/fixtures/` и тест в
   `tests/test_parsers.py`. Тесты не должны ходить в сеть.
5. Проверьте `robots.txt`, не обходите авторизацию, капчу и платные API.
6. Обновите таблицу магазинов в README.

Минимальный контракт:

```python
class MyShopParser(BaseParser):
    shop_id = "myshop"
    shop_name = "My Shop"
    sample_url = "https://myshop.example/item/123"

    def can_handle(self, url: str) -> bool:
        return host_of(url) == "myshop.example"

    async def parse(self, url: str) -> ParsedProduct:
        html = await self.fetch_text(url)
        ...
        return ParsedProduct(title=title, price=price, shop=self.shop_id)
```

## Как добавить команду бота

1. Добавьте метод `_cmd_<name>` в `app/bot/handlers.py`.
2. Опишите команду в `COMMANDS_HELP`.
3. Добавьте тест в `tests/test_bot.py` с `FakeAPI` — реальный Telegram не нужен.
4. Не выполняйте в обработчике долгие блокирующие операции; парсинг уже асинхронный.

## Коммиты и Pull Request

Используем [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat(parser): add DNS shop parser
fix(bot): handle expired callback queries
docs: describe Telegram setup
chore(deps): bump httpx
```

В PR заполните шаблон, приложите скриншот для UI-изменений и укажите, какие
проверки запускали. Один PR — одна логическая задача.

### Чек-лист

- [ ] Тесты добавлены или обновлены.
- [ ] `pytest`, `ruff`, `black` и `alembic check` проходят.
- [ ] Новые настройки описаны в `.env.example` и README.
- [ ] Для изменений схемы БД создана миграция.
- [ ] В коде нет токенов, паролей и персональных данных.

## Безопасность

Не открывайте публичный issue для уязвимостей. Используйте
[GitHub Security Advisories](https://github.com/HBBoy102011/price-pulse/security/advisories/new)
или инструкции из [SECURITY.md](SECURITY.md).

## Лицензия

Отправляя PR, вы соглашаетесь с тем, что ваш вклад распространяется под
[MIT License](LICENSE).
