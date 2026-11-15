# Architecture

The code sits in three rooms, and the dependencies point one way.

- **The application** is what matters: the ingest flow, the agent and its prompts, the rules
  that decide what a document is and whether an answer is verified. It holds the logic and
  nothing else. When it needs the outside world (a model, the database, a folder) it calls a
  port: a `Protocol` it defines itself, with plain types going in and out.
- **The adapters** are the pipes. Each one answers a port for one technology (Postgres, Mistral,
  docling, the embedder, the filesystem) and knows nothing of why it is called. The Postgres
  models and migrations live here, and the repository is where the application's plain
  `Document` becomes rows.
- **The hosts** are the plumbing: the commands, the MCP server and its auth, the config, and the
  wiring that builds the adapters and hands them to the application.

```mermaid
flowchart LR
    subgraph hosts["hosts · plumbing"]
        direction TB
        commands["librarian-ingest<br/>librarian-ask · librarian-trace"]
        serve["librarian-serve<br/>MCP · Cloudflare Access or bearer"]
        wiring["wiring · config"]
    end

    subgraph application["application · what matters"]
        direction TB
        ingest["ingest<br/>pipeline · parsers · drafter"]
        retrieve["retrieve<br/>refine · agent · verify · link"]
        ports{{"ports<br/>Protocols + plain types"}}
        ingest --- ports
        retrieve --- ports
    end

    subgraph adapters["adapters · pipes"]
        direction TB
        postgres[("Postgres<br/>pgvector")]
        mistral["Mistral<br/>chat · OCR"]
        docling["docling-serve"]
        tei["TEI · bge-m3"]
        folders[/"inbox · processed<br/>quarantine · traces"/]
    end

    commands --> application
    serve --> application
    wiring -. builds .-> adapters
    adapters -. answer .-> ports

    classDef host fill:#e9f7ef,stroke:#2e9e5b,color:#10301d
    classDef app fill:#e8f0fe,stroke:#3b6fd8,color:#0f2350
    classDef pipe fill:#fff3e0,stroke:#e08a1e,color:#3d2400
    class commands,serve,wiring host
    class ingest,retrieve,ports app
    class postgres,mistral,docling,tei,folders pipe
```

To change what the Librarian does, read the application. To change how it talks to a service,
read that one adapter. To change how it starts or what it is configured with, read the hosts.
The evals sit outside the package: they measure it, they don't ship with it.

**The import rule.** The application imports nothing from the adapters or the hosts, and nothing
of the database (`sqlalchemy`, `psycopg`); a test enforces it. Adapters don't read the config:
a host hands it to them. The one exception is alembic's `env.py`, an entry point that lives with
the migrations and reads the database URL the way a host does.

## Ingest

```mermaid
flowchart TD
    inbox[/"inbox/*.pdf"/] -->|"unchanged for 60 s"| read["docling<br/>elements: text · page · layer"]
    read --> claimed{"a parser knows<br/>the layout?"}

    claimed -->|yes| seenP{"same content<br/>already read?"}
    seenP -->|no| parser["parser · code<br/>fields read from the layout"]
    parser --> confirmed(["document · confirmed"])

    claimed -->|no| short{"a scan, or<br/>under 5 pages?"}
    short -->|yes| ocr["Mistral OCR<br/>markdown per page"]
    short -->|no| seenD
    ocr --> seenD{"same content<br/>already read?"}
    seenD -->|no| drafter["drafter · Mistral<br/>kind · validity · fields<br/>checked against the text, retried"]
    drafter --> draft(["document · draft"])

    seenP -->|yes| duplicate["duplicate<br/>row kept, file deleted"]
    seenD -->|yes| duplicate

    confirmed --> sections["sections, each whole"]
    draft --> sections
    sections --> chunks["chunks with their heading"]
    chunks --> embed["bge-m3 on TEI<br/>1024-d vectors"]
    embed --> store[("Postgres<br/>documents · sections · chunks<br/>vectors + Italian tsvector")]
    store --> processed[/"processed/kind/id.pdf"/]

    failed["any error, or<br/>5 paid calls spent"] --> quarantine[/"quarantine/id.pdf<br/>with the reason"/]

    classDef model fill:#fff3e0,stroke:#e08a1e,color:#3d2400
    classDef code fill:#e8f0fe,stroke:#3b6fd8,color:#0f2350
    classDef bad fill:#fdecea,stroke:#d93025,color:#4a0f0b
    class read,ocr,drafter,embed model
    class parser,sections,chunks code
    class failed,quarantine,duplicate bad
```

Every file gets an `ingestions` row, read or not; it is written when the file starts, and
finished with how it ended. A read file gets a `documents` row (kind, validity, fields), its
`document_sections` (each section whole) and their `chunks` (the embedded pieces). If the
final write fails, the file goes back to the inbox. A document gets at most 5 paid model calls
(OCR, drafter and every retry); past them it goes to quarantine.

**Embeddings.** Each section is split into chunks that fit bge-m3's budget (8192 tokens, less a
margin), by paragraph, then sentence, comma and word only when a piece is still too long; most
sections fit in one chunk. Each chunk keeps its section's heading on top, and is embedded by
bge-m3 on Text Embeddings Inference into a 1024-dimension vector (pgvector). Postgres also keeps
each chunk's text as an Italian `tsvector`, accents stripped, for keyword search.

## Retrieve

This is the Librarian's job: a question in, an answer with its sources out. Three parts, each
with one role, then code that checks what they produced:

```mermaid
flowchart LR
    question(["question<br/>in plain language"])

    subgraph rewriter["① query rewriter"]
        direction TB
        rewriteModel["one model call · Mistral Medium, pinned<br/>structured output, schema-checked, retried"]
        refined[/"queries<br/>each corrected, split out,<br/>with an exact period: from → to"/]
        rewriteModel --> refined
    end

    subgraph agentSide["② retrieval agent"]
        direction TB
        briefing[/"briefing<br/>the library: kinds, issuers, dates<br/>the schema: tables, fields<br/>context.md: who is who"/]
        agentModel["agent model · reasoning on<br/>at most 20 rounds<br/>picks a tool each round"]
        briefing --> agentModel
    end

    subgraph tools["③ tools"]
        direction TB
        search["search<br/>hybrid: keyword + vector<br/>→ top 5 whole sections"]
        sql["sql<br/>one SELECT as librarian_reader<br/>read-only · 5 s · 200 rows"]
        submit["submit<br/>status · values · passages · sources"]
    end

    subgraph checks["④ checked by code"]
        direction TB
        verify["verify<br/>a value is verified only if its<br/>document was read by a parser"]
        link["link<br/>section and document sizes,<br/>a link to the file"]
        verify --> link
    end

    result(["result<br/>found · partial · not_found<br/>+ trace_id"])

    tei["TEI · bge-m3"]
    chunks[("chunks<br/>pgvector + Italian tsvector")]
    fields[("documents · document_sections<br/>kind · validity · fields")]

    question --> rewriter
    refined --> agentModel
    agentModel <--> search
    agentModel <--> sql
    agentModel --> submit
    submit --> verify
    link --> result
    search -.- tei
    search -.- chunks
    sql -.- fields

    classDef model fill:#fff3e0,stroke:#e08a1e,color:#3d2400
    classDef tool fill:#e8f0fe,stroke:#3b6fd8,color:#0f2350
    classDef code fill:#e9f7ef,stroke:#2e9e5b,color:#10301d
    classDef store fill:#f1f3f4,stroke:#5f6368,color:#202124
    classDef io fill:#f3e8fd,stroke:#8e44ad,color:#2b0f3d
    class rewriteModel,agentModel model
    class search,sql,submit tool
    class verify,link code
    class refined,briefing,tei,chunks,fields store
    class question,result io
```

**① The query rewriter** is one call to its own model, with a schema the answer must fit. It
corrects the question's spelling, splits a question that is really several into queries, and
turns its time words ("quest'anno", "l'estate scorsa", "a maggio") into exact periods worked out
from today. An answer that doesn't fit the schema, or names a date that doesn't exist, is sent
back with the error. The model is pinned and measured by its own eval, so the agent's job is
finding, not interpreting.

**② The retrieval agent** is a second model, reasoning on, that digs until it can answer. It
starts briefed: the library's summary and the schema are in its prompt, so it spends no round
discovering them. Each round it picks a tool; on the last round `submit` is the only one left.

**③ The tools** split the work by what the documents hold:

- **sql** answers what the structured fields hold: totals, consumption, dates, counts across
  documents and years. It is safe by the database, not by inspecting the query: a role that can
  only read `documents` and `document_sections`, one statement per call, every call rolled back,
  the role's 5 s timeout, a 200-row cap enforced by Postgres, and our own clock that cancels a
  query past 8 s. A bad query comes back as the database's error, for the agent to read and fix.
- **search** finds what only the text says: a clause, a condition, a sentence to quote. It
  returns whole sections, with their document's kind, issuer, validity and status, so the agent
  reads the context, not a fragment.
- **submit** ends the dig with a status, the values, the passages that prove them, and their
  sources.

**④ Checked by code.** Verified comes from the document's status, never from the model: only a
value whose document was read by a parser is verified. Every value must name its source, each
source gets the sizes of what `get_section` and `get_document` return and a link to its file. A
question the documents don't answer ends `not_found`.

### Inside search

Both sides run in one SQL query:

```mermaid
flowchart LR
    query(["query"]) --> embed["embed<br/>bge-m3 · TEI"]
    query --> keyword["keyword side<br/>Italian tsquery, unaccented<br/>top 50 chunks"]
    embed --> vector["vector side<br/>cosine distance · pgvector<br/>top 50 chunks"]
    keyword --> fuse{{"reciprocal rank fusion<br/>k = 60"}}
    vector --> fuse
    fuse --> whole["each chunk → its whole section<br/>ranked by its best chunk"]
    whole --> top["top 5 sections<br/>with document, kind, issuer,<br/>validity, verified"]
    top --> trim["long ones trimmed to 2000 chars<br/>around the first query word"]
    trim --> seen["sections already returned<br/>come back as their id only"]
    seen --> agent(["to the agent"])

    classDef db fill:#fff3e0,stroke:#e08a1e,color:#3d2400
    classDef app fill:#e8f0fe,stroke:#3b6fd8,color:#0f2350
    class embed,keyword,vector,fuse,whole,top db
    class trim,seen app
```

Keyword search catches exact words and numbers; vector search catches the same meaning in other
words. The ranking is the adapter's SQL; trimming and the already-returned rule are the
application's, so the agent and the search eval see the same thing.

### Where it runs

```mermaid
flowchart LR
    you(("You")) <--> assistant["your AI assistant<br/>Claude · Mistral Vibe · …"]
    assistant -- "MCP over HTTPS" --> access["Cloudflare Access<br/>logs the caller in"]

    subgraph server["librarian-serve · one container"]
        auth["auth<br/>Access JWT, or bearer"] --> mcp["MCP server<br/>ask · get_section<br/>get_document · feedback"]
        mcp --> retrieve["retrieve<br/>① ② ③ ④"]
    end

    access --> auth
    retrieve -.-> mistral["Mistral API<br/>rewriter and agent models"]
    retrieve -.-> tei["TEI · bge-m3"]

    subgraph postgres["Postgres + pgvector"]
        library[("library<br/>documents · sections · chunks")]
        runs[("runs<br/>asks · events · feedback")]
    end

    retrieve -- "as librarian_reader" --> library
    retrieve -- "trace" --> runs
    mcp -- "feedback" --> runs
    ingest["librarian-ingest"] --> library
    assistant -. "file links" .-> files[/"processed PDFs"/]
    ingest --> files

    classDef actor fill:#f3e8fd,stroke:#8e44ad,color:#2b0f3d
    classDef host fill:#e9f7ef,stroke:#2e9e5b,color:#10301d
    classDef external fill:#fff3e0,stroke:#e08a1e,color:#3d2400
    classDef store fill:#f1f3f4,stroke:#5f6368,color:#202124
    class you,assistant actor
    class auth,mcp,retrieve,ingest host
    class access,mistral,tei external
    class library,runs,files store
```

The library is shared state: `librarian-ingest` writes it, an ask only reads it. What an ask
writes is its own record, the run and its events, to Postgres or to files
(`LIBRARIAN_TRACE_STORE`); feedback needs the Postgres one, since a rating points at its run.

### An ask's states

Each one is an event in its trace:

```mermaid
stateDiagram-v2
    [*] --> started
    started --> refine
    refine --> system: queries with periods
    system --> round: prompt built
    round --> round: search or sql
    round --> submitted: submit
    round --> finished: 20 rounds, no submit
    submitted --> verified
    verified --> linked
    linked --> finished
    refine --> failed
    system --> failed
    round --> failed
    verified --> failed
    linked --> failed
    finished --> [*]
    failed --> [*]

    note right of finished
        status found, partial or not_found,
        none without a submit
    end note
    note right of failed
        the error and the step it broke in;
        the caller still gets the error
    end note
```

**Tracing.** Every ask leaves a trace under its correlation id: each state above, every round's
thinking, tool calls and results, with their times. It goes to files or Postgres in batches, and
never breaks an ask; `librarian-trace <id>` prints it.
