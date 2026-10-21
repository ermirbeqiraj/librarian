# Librarian

Reads the documents dropped in a folder, works out what each one is, and stores
its fields, its sections and their embeddings in Postgres for search.

## Architecture

```
LIBRARIAN_ROOT/inbox/*.pdf
        │  polled every LIBRARIAN_POLL_SECONDS; a file must sit unchanged for 60 s
        ▼
  docling-serve ──► elements (text, page, layer)
        │
        ├─ known layout ──► parser (code) ───────────────► document, confirmed
        │
        └─ unknown ──► scan or < 5 pages? ──► Mistral OCR
                       │
                       └─► drafter (Mistral LLM + checks) ──► document, draft
        │
        │  content hash: already ingested? ──► duplicate, stop
        ▼
  sections ──► chunks ──► embedder (TEI, bge-m3) ──► Postgres + pgvector
        │
        ▼
  file moved to processed/{kind}/{id}.pdf, or quarantine/{id}.pdf
  when it is a duplicate or failed
```

Every file gets an `ingestions` row, read or not. A read file gets a `documents` row
(kind, validity, fields), its `document_sections` (each section whole) and their
`chunks` (the embedded pieces). If the database commit fails, the file goes back
to the inbox.

- **Ingestion** → `src/librarian/ingest/`
- **Adapters** → `src/librarian/adapters/`
- **Models** → `src/librarian/models/`
- **Migrations** → `src/librarian/migrations/`
- **Experiments** → `experiments/`

## Setup

Needs [uv](https://docs.astral.sh/uv/) and Docker.

```
uv sync
echo "MISTRAL_API_KEY=..." > .env
docker compose --profile eval up -d --wait
uv run alembic upgrade head
```

Compose starts Postgres with pgvector, docling-serve and the embedder. The
embedder sits behind the `eval` profile, and the pipeline needs it.

## Run

```
uv run --env-file .env librarian-ingest
```

Drop PDFs in `LIBRARIAN_ROOT/inbox/`. `uv run librarian` checks the database
connection.

Checks: `uv run ruff check .` · `uv run ruff format .` · `uv run pyright` · `uv run pytest`.

### As a container

Each push to `main` publishes `ghcr.io/ermirbeqiraj/librarian:latest`. On start it
migrates the database, then runs the pipeline. Mount the library folder at
`/library` and point the URLs below at the other services. It runs as uid 1000;
use `user:` in Compose if the library folder belongs to someone else.

## Environment

| Variable | Default | What |
|---|---|---|
| `MISTRAL_API_KEY` | none, required | Drafter and OCR |
| `LIBRARIAN_ROOT` | `~/.local/share/librarian`, `/library` in the image | Holds `inbox/`, `processed/`, `quarantine/` |
| `LIBRARIAN_DATABASE_URL` | `postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian` | Postgres |
| `LIBRARIAN_DOCLING_URL` | `http://127.0.0.1:5001` | docling-serve |
| `LIBRARIAN_EMBEDDER_URL` | `http://127.0.0.1:8083` | Text Embeddings Inference running bge-m3 |
| `LIBRARIAN_POLL_SECONDS` | `10` | Seconds between inbox checks |
