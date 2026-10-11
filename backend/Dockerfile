FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY detour ./detour
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 DETOUR_DATA_DIR=/tmp/detour
EXPOSE 8000
CMD ["sh", "-c", "uvicorn detour.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
