# Run

## What you need

For both:

- **A Mistral API key.** The OCR, the drafter, the query rewriter and the agent call it.
- **An AI assistant that speaks MCP** (Claude, Mistral Vibe, …), to ask the Librarian questions.

On a dev machine:

- **[uv](https://docs.astral.sh/uv/)**, for Python and the dependencies.
- **Docker with Compose**, for Postgres (with pgvector), docling-serve and the embedder.

For production:

- **A server with Docker**, to run the published image.
- **Postgres with the `vector` and `unaccent` extensions**, and a read-only `librarian_reader`
  role for the agent's SQL. Migrations create neither: a superuser creates both extensions
  before the first migration, and infra provisions the role (`SELECT` on `documents` and
  `document_sections`, read-only, a 5 s `statement_timeout`).
- **docling-serve and Text Embeddings Inference running bge-m3**, reachable from the server.
- **Cloudflare Access** in front of the MCP endpoint, so the Librarian keeps no logins of its
  own: you need the Access team name and the application's AUD tag.

## On a dev machine

Set up once:

```
uv sync
echo "MISTRAL_API_KEY=..." > .env
docker compose -f infra/compose.yaml up -d --wait
uv run alembic upgrade head
```

Compose creates the extensions on a fresh volume (`infra/postgres/extensions.sql`). Everything
the Librarian keeps lives under `LIBRARIAN_ROOT`, `~/.local/share/librarian` by default:
`inbox/`, `processed/`, `quarantine/`, `traces/`, `evals/`, and an optional `context.md`,
written by hand, that tells the agent who the people, homes and things in the documents are.

Fill the library: drop a few PDFs of your own in `LIBRARIAN_ROOT/inbox/`, then

```
uv run --env-file .env librarian-ingest --once
```

It processes what is in the inbox, waiting for files still being written, then exits; without
`--once` it watches the inbox until stopped.

Ask a question from the command line:

```
uv run --env-file .env librarian-ask --model deepseek-v4-1-flash-1017 "how has the electricity spending changed this year?"
uv run librarian-trace <correlation id>
```

`librarian-ask` prints its correlation id on stderr, then the refined queries, the result and
the totals as JSON. `librarian-trace` prints that ask's trace as a tree; `--full` prints it all.

Ask it from your assistant: serve it locally with a bearer token, and add
`http://127.0.0.1:8090/mcp` to your assistant as an MCP server with the header
`Authorization: Bearer <token>`.

```
LIBRARIAN_AUTH=bearer LIBRARIAN_BEARER_TOKEN=<32 characters or more> \
  uv run --env-file .env librarian-serve
```

Check it: `uv run ruff check .` · `uv run ruff format .` · `uv run pytest`. The database tests
run on a throwaway `librarian_test` database on the compose Postgres, and set up its reader role
themselves.

## In production

Each push to `main` publishes `ghcr.io/ermirbeqiraj/librarian:latest`, and the commit's sha as
a tag to roll back to. The image runs as uid 1000 and keeps its library at `/library`; mount a
folder there, and use `user:` if that folder belongs to someone else.

The same image runs both services:

- **ingest**, the image's default: it migrates the database, then watches `/library/inbox`.
- **serve**, with `librarian-serve` as the command: the MCP endpoint, behind Cloudflare Access.

```yaml
services:
  librarian-ingest:
    image: ghcr.io/ermirbeqiraj/librarian:latest
    env_file: librarian.env
    volumes:
      - /srv/library:/library

  librarian-serve:
    image: ghcr.io/ermirbeqiraj/librarian:latest
    command: librarian-serve
    env_file: librarian.env
    environment:
      LIBRARIAN_SERVE_HOST: 0.0.0.0
    volumes:
      - /srv/library:/library
```

with `librarian.env` holding at least:

```
MISTRAL_API_KEY=...
LIBRARIAN_DATABASE_URL=postgresql+psycopg://librarian:...@db:5432/librarian
LIBRARIAN_READER_DATABASE_URL=postgresql+psycopg://librarian_reader:...@db:5432/librarian
LIBRARIAN_DOCLING_URL=http://docling:5001
LIBRARIAN_EMBEDDER_URL=http://embedder:80
LIBRARIAN_TRACE_STORE=postgres
LIBRARIAN_AUTH=access
LIBRARIAN_ACCESS_TEAM=<team>
LIBRARIAN_ACCESS_AUD=<aud tag>
```

Point a Cloudflare Access application at the serve container's port (8090), and give your
assistant that public URL with `/mcp`. Every request passes the auth before MCP sees it: the
server checks Access's `Cf-Access-Jwt-Assertion` against the team's keys, the issuer and the
AUD tag, and answers 403 otherwise. It doesn't start without a complete auth.

`LIBRARIAN_TRACE_STORE=postgres` keeps every ask's trace in the database, which `feedback`
needs: a rating points at its run. `LIBRARIAN_FILE_URL` adds a link to each source's file, if
something serves the processed PDFs.

## Configuration

| Variable | Default | What |
|---|---|---|
| `MISTRAL_API_KEY` | none, required | OCR, drafter, query rewriter and agent |
| `LIBRARIAN_ROOT` | `~/.local/share/librarian`, `/library` in the image | The library's folders |
| `LIBRARIAN_DATABASE_URL` | `postgresql+psycopg://librarian:librarian@127.0.0.1:5432/librarian` | Postgres |
| `LIBRARIAN_READER_DATABASE_URL` | `postgresql+psycopg://librarian_reader:librarian_reader@127.0.0.1:5432/librarian` | The agent's read-only connection; set it wherever `LIBRARIAN_DATABASE_URL` is set |
| `LIBRARIAN_DOCLING_URL` | `http://127.0.0.1:5001` | docling-serve |
| `LIBRARIAN_EMBEDDER_URL` | `http://127.0.0.1:8083` | Text Embeddings Inference running bge-m3 |
| `LIBRARIAN_AGENT_MODEL` | `deepseek-v4-1-flash-1017` | The agent's model in `librarian-serve` |
| `LIBRARIAN_TRACE_STORE` | `file` | `file` (`LIBRARIAN_ROOT/traces/<id>.jsonl`) or `postgres` (`asks`, `ask_events`) |
| `LIBRARIAN_FILE_URL` | none | A link to a source's file, with `{path}` for its path under the root |
| `LIBRARIAN_SERVE_HOST` | `127.0.0.1` | Where `librarian-serve` listens |
| `LIBRARIAN_SERVE_PORT` | `8090` | Its port |
| `LIBRARIAN_AUTH` | none, required by `librarian-serve` | `access` or `bearer` |
| `LIBRARIAN_ACCESS_TEAM` | none | For `access`: the `<team>` of `<team>.cloudflareaccess.com` |
| `LIBRARIAN_ACCESS_AUD` | none | For `access`: the Access application's AUD tag |
| `LIBRARIAN_BEARER_TOKEN` | none | For `bearer`: 32 characters or more; 401 without it |
