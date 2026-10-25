FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/app/.venv/bin:$PATH \
    LIBRARIAN_ROOT=/library

WORKDIR /app

# Dependencies first, so a code-only change rebuilds from here down.
COPY pyproject.toml uv.lock README.md .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# Owns the files it moves in the mounted library; the homeserver can override with user:.
RUN useradd --uid 1000 --create-home librarian
USER librarian

CMD ["sh", "-c", "alembic upgrade head && exec librarian-ingest"]
