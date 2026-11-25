# Production runbook

For the operator moving the Librarian onto a target host. Steps run in order — each
produces what the next consumes. Every command is written out; everything in `<angle
brackets>` is a value of the target's, filled where it lands. Values and identifiers never
enter this repo.

## Inventory — what the deploy brings

One image, two hosts: the Api runs it by its default entrypoint, the Ingest overrides to
`ingest/Ingest.dll`. Pull it with the target's container runtime — the pull is anonymous,
the package public; pin the sha, `latest` only points:

    <runtime> pull ghcr.io/ermirbeqiraj/librarian:<sha>

The production configuration, one example per host — the templates the overlays are filled
from in [step 4](#4-the-overlays):

- [`Api/appsettings.Production.example.json`](../src/librarian/Api/appsettings.Production.example.json)
- [`Ingest/appsettings.Production.example.json`](../src/librarian/Ingest/appsettings.Production.example.json)

The instruction texts `ask-v2.md`, `refine-v3.md`, `extract.md`, `server.md` — carried from
the maintainer's planning side (`evals/instructions/` there; the repo never held them); they
land in the documents root in [step 2](#2-the-documents-root).

## Dependencies — the environment provides them; the deploy consumes their addresses

| dependency | provides | fills |
|---|---|---|
| Postgres with `vector` + `unaccent` | the library's store | `ConnectionStrings:Postgres`, `ConnectionStrings:PostgresReader` — prepared in [step 1](#1-postgres) |
| docling | document conversion for the ingest readers; HTTP endpoint, sync wait ≥ 300 s. Dev pin in `infra/compose.yaml` (`docling-serve-cpu:v1.36.0`) | `Ingest:Docling:Url` |
| bge-m3 | embeddings for ingest and search; HTTP endpoint serving BAAI/bge-m3. Dev pin in `infra/compose.yaml` (`text-embeddings-inference:cpu-1.9.4`) | `Store:Embedding:Url` in both overlays |
| cloudflared tunnel | the public hostname, routed to the api's published port | nothing in the overlays — [step 3](#3-cloudflare) |
| Cloudflare Access | the JWT gate in front of the api; the app validates its JWTs | `Auth:Access` in the api overlay — [step 3](#3-cloudflare) |

## Steps

### 1. Postgres

**Produces:** `<owner>` and `<reader>` — the two connection strings.

The SQL lives in [`infra/postgres/`](../infra/postgres), in this order. Run each file against
the target's Postgres with whatever client you use, as the superuser, stopping on the first
error; against the `librarian` database where noted. Passwords are set by hand in your
client and never enter a file.

1. [`create-login.sql`](../infra/postgres/create-login.sql) — the main login `librarian`.
2. [`create-db.sql`](../infra/postgres/create-db.sql) — the `librarian` database, owned by the login, locked to it.
3. [`extensions.sql`](../infra/postgres/extensions.sql) — `vector` + `unaccent`, against the `librarian` database; verify with `\dx`.

The migrations are not a step: the Ingest host runs them on its first start ([step 5](#5-both-hosts-up)).

`<owner>` and `<reader>` carry the address the app hosts reach postgres at — a shared
network or the postgres host itself, the target's own convention.

### 2. The documents root

**Produces:** `<root>`, mounted at `/data` in both app hosts.

    <root>/
    ├── inbox/
    ├── processed/                  ← filed as <kind>/<yyyy-MM>/<ingestionId>.<ext>
    ├── quarantine/                 ← failed/given-up files as <yyyy-MM>/<id>.<ext> (or original name on give-up)
    ├── results/
    ├── documents/
    └── instructions/
        ├── ask-v2.md
        ├── refine-v3.md
        ├── extract.md
        └── server.md

No runtime state files live in the root (the old `ocr-calls.json` is gone; OCR errors are
retried 3 times, then the file is quarantined).

### 3. Cloudflare

**Produces:** `<hostname>`, `<team>`, `<aud>`.

Cloudflare first, the Api second — the Api refuses to start without `Auth:Access`. In the
Zero Trust dashboard (or the Cloudflare API / its MCP server):

1. **Tunnel**: Networks → Tunnels → the target's tunnel → Public Hostnames → add `<hostname>`,
   service HTTP `localhost:5080` (the api's published port, [step 5](#5-both-hosts-up)).
2. **Access application**: Access → Applications → Add → Self-hosted, domain `<hostname>`.
   - Policy: one Allow policy with the operators' emails (or attach an existing reusable one).
   - Login methods: enable at least one IdP (one-time PIN and/or Google) on the app
     (`allowed_idps`); empty means no login and the auth fails. Session duration: 1 month.
   - Note the app's **Audience** (the AUD tag) and the team domain `<team>.cloudflareaccess.com`
     (start of the dashboard URL) — they go into the api overlay's `Auth:Access`.
3. **MCP clients (managed OAuth on the same app)**: set `oauth_configuration.enabled: true` on
   the application — opt-in for self-hosted apps. The Api code is unchanged; the edge still
   mints the same JWT to the origin. Non-browser clients then get `401` with
   `WWW-Authenticate: Bearer ... resource_metadata="https://<hostname>/.well-known/cloudflare-access-protected-resource/mcp"`,
   discovery via `authorization_servers: https://<team>.cloudflareaccess.com`
   (`/cdn-cgi/access/oauth/{registration,authorization,token}`); authorization needs PKCE (S256)
   and `resource=https://<hostname>/mcp`.
   - Clients without Dynamic Client Registration need a **static client**: POST one to the
     registration endpoint with the client's redirect URI (e.g. Mistral's
     `https://callback.mistral.ai/v1/integrations_auth/oauth2_callback`) and
     `resource=https://<hostname>/mcp`; give the connector the returned `client_id`.
   - Non-localhost redirect URIs are rejected until added to the app's
     `oauth_configuration.dynamic_client_registration.allowed_uris`. The registration endpoint
     has no PUT — re-register a new client instead of updating.
   - Do NOT add a second hostname (e.g. `mcp.<domain>`) to the tunnel for a portal-style setup:
     tunnel-forwarded traffic reaches the origin and the app 401s it.

From outside, before any Api runs:

    curl -sI https://<hostname>          # 302 → the Access login wall
    # a session behind that → origin error: routing and gate ready, nothing listening yet

### 4. The overlays

**Produces:** the two `appsettings.Production.json` files, `chmod 600`, outside every repo.

From the target's compose folder, copy the two examples from the Inventory and fill every
placeholder:

    mkdir -p api ingest
    cp <repo>/src/librarian/Api/appsettings.Production.example.json api/appsettings.Production.json
    cp <repo>/src/librarian/Ingest/appsettings.Production.example.json ingest/appsettings.Production.json
    chmod 600 api/appsettings.Production.json ingest/appsettings.Production.json

| placeholder | filled from |
|---|---|
| `<postgres>`, `<port>`, `<owner password>` | step 1 |
| `<reader password>` | step 5 |
| `<key>` | the Mistral API key |
| `<docling>`, `<bge-m3>` | the Dependencies table's addresses |
| `<team>`, `<aud>` | step 3 |
| `<root>` | step 2 |

The overlay overrides the base `appsettings.json` baked into the image; `Librarian:Root` is
`/data` in both examples — the mount in step 5. The `Auth:Access` side incomplete → the Api
refuses to start (open is not an option); `CertsUrl` stays unset unless the default
`https://<team>/cdn-cgi/access/certs` needs overriding. The Api writes its own rows (asks,
spans) over `Postgres`; the library is written by Ingest alone; the reader sees only
`documents, fields, sections` — the database enforces it.

### 5. Both hosts up

The image ships `DOTNET_ENVIRONMENT=Production`; nothing may ever set `Development`. The
target's own way of running the two services leads; in compose syntax they look like this:

    services:
      api:
        image: ghcr.io/ermirbeqiraj/librarian:<sha>
        environment:
          ASPNETCORE_ENVIRONMENT: Production
        ports:
          - "127.0.0.1:5080:5080"
        volumes:
          - ./api/appsettings.Production.json:/app/api/appsettings.Production.json:ro
          - <root>:/data:ro
        restart: unless-stopped
      ingest:
        image: ghcr.io/ermirbeqiraj/librarian:<sha>
        entrypoint: ["dotnet", "ingest/Ingest.dll"]
        volumes:
          - ./ingest/appsettings.Production.json:/app/ingest/appsettings.Production.json:ro
          - <root>:/data
        restart: unless-stopped

The Ingest host applies the migrations on its first start, as the `librarian` login, so the
objects land owned by it — nothing to run by hand. Once its log shows the inbox watch, run
[`create-reader.sql`](../infra/postgres/create-reader.sql) against the `librarian` database
(its grants name real tables) and set the reader's password by hand; the Api picks the reader
up on its next query.

The image has no curl, so the healthchecks live outside the app hosts: `curl` the published
port, read the logs.

### 6. Prove

From outside, a Cloudflare session in hand:

    curl -sI https://<hostname>                     # no session: the wall — never the Api
    # session: /health → 200 through the tunnel; /whoami → the Access JWT's raw claims
    curl -s -o /dev/null -w '%{http_code}\n' \
      -H 'Authorization: Bearer wrong' https://<hostname>/whoami   # 401

On the target:

    curl -fsS http://127.0.0.1:5080/health           # 200

Then the ingest host's logs (your runtime's logs command): the 30 s scan tick, empty inbox.

The library starts empty; ingesting documents and pointing a client at `/mcp` come after
the gate is proved.
