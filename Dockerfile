FROM python:3.12-slim

LABEL org.opencontainers.image.title="PricePulse" \
      org.opencontainers.image.description="Price tracker with shop parsers, history, Chart.js dashboard and Telegram bot" \
      org.opencontainers.image.source="https://github.com/HBBoy102011/price-pulse" \
      org.opencontainers.image.url="https://github.com/HBBoy102011/price-pulse" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/api/health" || exit 1

# Apply migrations, then serve. Works with SQLite, PostgreSQL and PaaS $PORT.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
