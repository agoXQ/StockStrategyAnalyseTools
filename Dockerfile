# syntax=docker/dockerfile:1

FROM node:26-slim AS frontend-builder
WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_URL=sqlite:////data/stock_strategy.db \
    CONFIG_FILE=/app/config.yaml \
    CORS_ALLOW_ORIGINS=* \
    BOOTSTRAP_FIRST_USER_AS_ADMIN=true

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data /app

COPY requirements.txt ./
ARG MARKET_EXTRAS=""
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && if [ -n "$MARKET_EXTRAS" ]; then pip install --no-cache-dir $MARKET_EXTRAS; fi

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser config.yaml ./config.yaml
COPY --chown=appuser:appuser stock_strategy_tool_database_schema.sql ./stock_strategy_tool_database_schema.sql
COPY --chown=appuser:appuser --from=frontend-builder /build/frontend/dist ./frontend/dist

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
