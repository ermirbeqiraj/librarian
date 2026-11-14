The plan: [docs/project.md](docs/project.md).

Run it: `docker compose up -d --wait` · `uv run alembic upgrade head` · `uv run librarian-ingest`.
Check it: `uv run ruff check .` · `uv run ruff format .` · `uv run pyright` · `uv run pytest`.

No document or personal data goes in this repo, not even in a test fixture.

The task files, evals and notes live outside this repo, because it's public. Where they are is in
`CLAUDE.local.md` (not committed). If it's missing, ask before starting a task.

Branches: work branches off `develop`, one PR per task into `develop`, squash-merged. `develop` goes
to `main` only after the full `uv run pytest` runs green against real Postgres (compose up, migrated
to head): a DB test that skips is untested. Each push to `main` publishes the image.
