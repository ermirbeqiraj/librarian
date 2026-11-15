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

Migrations create no roles and no extensions. Dev compose creates the `vector` and
`unaccent` extensions on a fresh volume (`dev/extensions.sql`); on any other Postgres,
a superuser creates both in the database before the first `alembic upgrade head`.

## Run

```
uv run --env-file .env librarian-ingest
```

Drop PDFs in `LIBRARIAN_ROOT/inbox/`. It watches the inbox until stopped; with `--once` it
processes what is there, waiting for files still being written, then exits. A document
gets at most 5 paid Mistral calls (OCR, drafter and every retry); past them it goes to
quarantine. `uv run librarian` checks the database connection.

`uv run --env-file .env librarian-ask --model <model> "qnd scade la bolletta"` asks one question
and prints its correlation id (`ask-<time>-<6 hex>`, on stderr), then the refined queries, the
result and the totals as JSON. There is no default model. Every run, from the command or the
eval, leaves a trace under its correlation id: each step it went through, in order, with its
time (refine, the system text, every round's thinking, tool calls and results, what was
submitted and verified, how it ended). `LIBRARIAN_TRACE_STORE` picks where: `file` keeps
`LIBRARIAN_ROOT/traces/<id>.jsonl`, `postgres` the `asks` and `ask_events` tables.
`uv run librarian-trace <id>` prints one trace as a tree, long text cut to a few lines;
`--full` prints it all.
`uv run --env-file .env librarian-serve` serves `ask` to an outside agent over MCP (streamable
HTTP at `/mcp`, on `LIBRARIAN_SERVE_HOST:LIBRARIAN_SERVE_PORT`). Its agent model is
`LIBRARIAN_AGENT_MODEL`; each ask's correlation id is `mcp-<time>-<6 hex>`, returned as
`trace_id`. Every request passes the auth before MCP sees it, and the server doesn't start
without one: `LIBRARIAN_AUTH=bearer` wants `Authorization: Bearer <LIBRARIAN_BEARER_TOKEN>` (401
otherwise), `LIBRARIAN_AUTH=access` wants Cloudflare Access's `Cf-Access-Jwt-Assertion`, checked
against the team's keys, issuer and the app's AUD tag (403 otherwise).
Each source in the result carries its `section_id` (null for a row from SQL), the lengths of
its section and its document in characters, and `file`: `LIBRARIAN_FILE_URL` with `{path}`
replaced by the processed file's path under `LIBRARIAN_ROOT`, quoted (null when unset).
`get_section(section_id)` returns a section's whole text under its heading,
`get_document(document_id)` a document's sections in order; both read as `librarian_reader`.
`feedback(trace_id, rating, note)` rates an answer `good` or `bad` in `ask_feedback`; it needs
`LIBRARIAN_TRACE_STORE=postgres`, since the rating points at the run's `asks` row.
An optional `LIBRARIAN_ROOT/context.md`, written by hand, tells the agent who the people,
homes and things in the documents are; it goes into the agent's instructions as is.

`uv run --env-file .env librarian-eval-retrieval --cases <file>` asks every case in
`LIBRARIAN_ROOT/evals/retrieval/<file>` through the whole pipeline and scores what the
result says (the value, the quote, the status), not which document it came from.
`--model` (required) picks the agent's model, `--question N` asks only the case at position N (from 0),
`--repeat N` asks each question N times. Each run writes `runs/run-<time>.md`, the summary
it also prints, and `runs/run-<time>/` with every question's case, marks and inquiry. Each
ask's correlation id is `run-<time>-q<NN>-r<N>` (case, attempt), in its row of the summary.

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
| `LIBRARIAN_ROOT` | `~/.local/share/librarian`, `/library` in the image | Holds `inbox/`, `processed/`, `quarantine/`, `evals/`, `traces/` |
| `LIBRARIAN_DATABASE_URL` | `postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian` | Postgres |
| `LIBRARIAN_READER_PASSWORD` | `librarian_reader` (dev only) | Password of the read-only `librarian_reader` role the SQL tool connects as. The role itself is provisioned outside the app — by infra on the homeserver, by the test setup in dev; no migration creates roles — so set the password on the homeserver |
| `LIBRARIAN_READER_DATABASE_URL` | `LIBRARIAN_DATABASE_URL` as `librarian_reader` | The SQL tool's read-only connection |
| `LIBRARIAN_DOCLING_URL` | `http://127.0.0.1:5001` | docling-serve |
| `LIBRARIAN_EMBEDDER_URL` | `http://127.0.0.1:8083` | Text Embeddings Inference running bge-m3 |
| `LIBRARIAN_POLL_SECONDS` | `10` | Seconds between inbox checks |
| `LIBRARIAN_TRACE_STORE` | `file` | Where every ask's trace goes: `file` or `postgres` |
| `LIBRARIAN_FILE_URL` | none | A link to a document's file, with `{path}` in it; unset, sources have no link |
| `LIBRARIAN_AGENT_MODEL` | `deepseek-v4-1-flash-1017` | The agent's model in `librarian-serve` |
| `LIBRARIAN_SERVE_HOST` | `127.0.0.1` | Where `librarian-serve` listens |
| `LIBRARIAN_SERVE_PORT` | `8090` | Its port |
| `LIBRARIAN_AUTH` | none, required by `librarian-serve` | `bearer` or `access` |
| `LIBRARIAN_BEARER_TOKEN` | none | The token `bearer` wants, 32 characters or more |
| `LIBRARIAN_ACCESS_TEAM` | none | The Access team for `access`: only the `<team>` of `<team>.cloudflareaccess.com` |
| `LIBRARIAN_ACCESS_AUD` | none | The Access application's AUD tag, for `access` |
