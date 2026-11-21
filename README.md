# librarian

An agent that knows everything about the documents you give it.

Drop PDFs (bills, receipts, contracts) in a folder. The Librarian reads each one, works out what
it is and stores its fields and its text in Postgres. Then you ask it questions in plain language,
and it answers with the values and the passages they come from, saying which ones were read by
code and which by a model. Other agents can ask it too, over MCP.

## Where things are

| | |
|---|---|
| [`python/`](python/README.md) | The first version, in Python. Kept for reference while it's rewritten in .NET, then removed. |
| `infra/` | Compose for the local services (Postgres, docling, the embedder), and the database setup. |

## License

MIT, see [LICENSE](LICENSE).
