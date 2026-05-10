FROM python:3.13-slim AS base
WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml uv.lock ./

# --- deps layer (cached unless pyproject.toml / uv.lock change) ---
FROM base AS deps
RUN uv sync --frozen --no-dev --no-install-project

# --- app layer ---
FROM deps AS app
COPY durgam/ durgam/
COPY scripts/ scripts/
COPY rxconfig.py ./
COPY alembic.ini ./
COPY alembic/ alembic/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3000 8000
