# librarian

An agent that knows everything about the documents you give it.

Drop PDFs (bills, receipts, contracts) in a folder. The Librarian reads each one, works out what
it is and stores its fields and its text in Postgres. Then you ask it questions in plain language,
and it answers with the values and the passages they come from, saying which ones were read by
code and which by a model. Other agents can ask it too, over MCP.

## Where things are

| | |
|---|---|
| `librarian/application/` | What it does: ingest (a file in, a document stored) and retrieve (a question in, an answer with its sources out). Start here. |
| `librarian/adapters/` | How it talks to the outside: Postgres, Mistral, docling, the embedder, the folders. |
| `librarian/hosts/` | How it starts: the commands, the MCP server, config, and the wiring between them. |
| `evals/` | How its quality is measured. Dev tools, not shipped. |
| `infra/` | Compose for local services, the Dockerfile. |
| `tests/` | The same tree as `librarian/`. |

## Docs

- [vision.md](docs/vision.md): what it is for and how it grows.
- [architecture.md](docs/architecture.md): the three rooms, the ports between them, the flow.
- [run.md](docs/run.md): get started, configure, run it for a demo and for real.
- [evals.md](docs/evals.md): how quality is measured, and how to run each eval.

## Quick start

Needs [uv](https://docs.astral.sh/uv/) and Docker, and a Mistral API key.

```
uv sync
echo "MISTRAL_API_KEY=..." > .env
docker compose -f infra/compose.yaml up -d --wait
uv run alembic upgrade head
uv run --env-file .env librarian-ingest --once
```

The rest is in [run.md](docs/run.md).

## License

MIT, see [LICENSE](LICENSE).
