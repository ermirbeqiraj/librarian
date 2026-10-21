The plan: [docs/project.md](docs/project.md).

Run it: `docker compose up -d --wait` · `uv run alembic upgrade head` · `uv run librarian-ingest`.
Check it: `uv run ruff check .` · `uv run ruff format .` · `uv run pyright` · `uv run pytest`.

No document or personal data goes in this repo, not even in a test fixture.
