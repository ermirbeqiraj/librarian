# Evals

Each part of the pipeline that a model or a ranking decides is measured on its own, so a change
shows where it helped or hurt. From the document in to the answer out:

| Eval | What it measures | Score |
|---|---|---|
| **drafter** | Reading a document no parser knows: kind, validity, fields | kind and validity right, fields found, attempts, problems left |
| **search** · `vector` | The embeddings alone: does the meaning find the right section? | rank of the first section holding the quote: top 1, top 5 |
| **search** · `keyword` | The text search alone: do the words find it? | same |
| **search** · `hybrid` | Both, merged as the agent gets them | same |
| **refine** | The query rewriter: the question split right, its dates exact | queries per question, each query's period |
| **retrieval** | The whole ask, rewriter, agent and tools together | answer, honesty, hit |

Read them bottom up when something breaks: a retrieval miss whose section search can't find is
a search problem; one where search finds it and the agent doesn't is the agent's.

## Cases and runs

> **Note.** The documents are confidential, and so are the cases written about them. Both live
> outside this repo, under the folder `LIBRARIAN_ROOT` names: each eval reads its cases from
> `LIBRARIAN_ROOT/evals/<name>/` and writes every run under `runs/` there.

Each run records the commit it ran from. The evals are dev tools in `evals/`, outside the
shipped package, and each runs as `python -m evals.<name>`. Those that call a model need
`MISTRAL_API_KEY` (`--env-file .env`).

## drafter

```
uv run --env-file .env python -m evals.drafter
```

Every case in `evals/drafter/*.json` names its PDF, its reader (`docling` or `mistral-ocr`, the
text cached beside the case), the model, the prompt version and the retries, and the kind,
validity and number of fields it expects. Each run writes `runs/<time> <case>.json` with the
prompt, the text and every attempt with its problems.

## search

```
uv run python -m evals.search --mode vector
uv run python -m evals.search --mode keyword
uv run python -m evals.search --mode hybrid --limit 5
```

Every case in `evals/search/*.json` is a question and the quotes that answer it. The question
goes to search as is, and the score is the rank of the first section holding a quote, as top 1
and top 5, per author. The modes isolate the sides: `vector` is the embedder, `keyword` the
Italian text search, `hybrid` what the agent sees. The vector side needs the embedder running.

## refine

```
uv run --env-file .env python -m evals.refine [--model <model>] [filter]
```

Every case in `evals/refine/questions.json` is a question, the day it is asked, and the queries
it should become. The score is the number of queries and each query's period; the text is not
scored but printed next to the expected one, to read. `filter` runs only the cases whose
question contains it.

## retrieval

```
uv run --env-file .env python -m evals.retrieval --cases <file> --model <model>
```

Every case in `evals/retrieval/<file>` is a question and what the answer must hold: a value, a
quote, or a status. Each question goes through the whole ask, and the result is scored on what
it says, not on which document it came from:

- **answer**: the expected value or quote is in the result;
- **honesty**: the status is the expected one (`found`, `partial` or `not_found`);
- **hit**: both.

`--question N` asks only the case at position N (from 0), `--repeat N` asks each question N
times. An ask that raises (a 429, a timeout) is skipped and counts in no score. Each run writes
`runs/run-<time>.md`, the summary it also prints, and `runs/run-<time>/` with every question's
case, marks and inquiry. Each ask's correlation id is `run-<time>-q<NN>-r<N>`;
`librarian-trace <id>` shows every step it went through.
