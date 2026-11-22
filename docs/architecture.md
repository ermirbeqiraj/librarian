# Architecture

The in-repo map of how this project is driven. The product description and the task series live
outside this public repo (see `CLAUDE.local.md`). `python/` is the first version, reference only
until the cutover; `infra/` is the shared compose for the local services.

## Layout

```
dotnet/                        the .NET app
├── Librarian.slnx
├── Directory.Build.props      net10.0, nullable, warnings as errors, CPM, lock files (locked mode)
├── Directory.Packages.props   exact package versions
├── nuget.config               nuget.org only, signatures required, trusted signers pinned
├── Dockerfile.dev             the dev image for compose: the .NET 10 runtime only — the host's
│                              build output is bind-mounted over /app (see infra/compose.yaml)
├── src/
│   ├── Librarian.Application  the brain: Ports/{Feature}/, Handlers/{Feature}/,
│   │                          Domain/, Services/ when the first shared service exists;
│   │                          references only abstractions (a test enforces it):
│   │                          EF Core, Microsoft.Extensions.AI, MAF — never a vendor
│   │                          package (Npgsql, Pgvector, OpenAI)
│   ├── Librarian.Adapters     one directory per technology (Docling/, Mistral/,
│   │                          FileSystem/, Postgres/); → Application
│   ├── Librarian.Evals        the eval runner, a dev tool never shipped: one subcommand per
│   │                          eval leg (`search` first); cases and runs live outside the repo,
│   │                          their root in the dev overlay (Evals:Root); → Application, Adapters
│   ├── Librarian.Ingest       worker host, scans the inbox on a timer; → Application, Adapters
│   └── Librarian.Api          ASP.NET Core host; → Application, Adapters
└── tests/Librarian.Tests      xUnit v3
```

References point one way: hosts → Application and Adapters; Adapters → Application. Two programs,
each its own container at deploy: only Ingest gets the inbox mounted; Api cannot write to the library.

## Domain

The domain classes live in Application, in `Domain/`; no project of their own. Rules for every
domain class:

- Created only through a factory named `Create` (`Document.Create(...)`, `Ingestion.Create(...)`);
  the constructor is private (a private parameterless one exists for EF Core).
- No public setters anywhere. State changes through methods named for what they do.
- Rich: the rules about a class's state live in the class, not in the handler.
- Enums are stored and read as strings (`HasConversion<string>()`), never as numbers.
- Plain C#: no base classes, no attributes for persistence. EF Core maps them from configuration.

Database access is EF Core used directly from the handlers: one `DbContext` in Application
(`Domain/LibrarianDbContext.cs`), no repository or unit of work on top. The context applies the
`IModelConfiguration`s it is given; the mapping that needs vendor types (the `vector` and
`tsvector` columns are Npgsql types) lives in Adapters, in `Postgres/`. Npgsql is wired in
Adapters (`AddPostgres`: `AddDbContext` with `UseNpgsql` + `UseVector`, migrations assembly
`Librarian.Adapters`).

## Conventions

Code shape, where things belong and the no-comment rule: [code-style.md](code-style.md).
Config, branches, packages and the build are below.

## Packages

- Exact versions, central (`Directory.Packages.props`); per-project `packages.lock.json`, restore
  always locked (`dotnet restore --locked-mode`; generate the locks once with
  `-p:RestoreLockedMode=false`).
- `nuget.config`: nuget.org only, `signatureValidationMode=require`, trusted signers pinned by
  SHA-256 fingerprint. Prove a bump with `dotnet nuget verify --all` on the restored packages; a
  bump goes on its own branch.

## Config

Each program reads `appsettings.json` — only what is identical in every environment, never a
connection string, machine path or secret — then `appsettings.{Environment}.json`, then
environment variables (`__` is `:`; env wins). No `.env` files. Anything that can change from
one environment to another (a connection string among them) lives only in the overlay or the
environment. The dev overlay `appsettings.Development.json` is gitignored; its keys:

    // src/Librarian.Ingest/appsettings.Development.json
    { "Librarian": { "Root": "/home/USER/.local/share/librarian-dotnet-dev" },
      "Mistral": { "ApiKey": "..." },
      "ConnectionStrings": { "Postgres": "Host=127.0.0.1;Port=5432;Database=librarian;Username=librarian;Password=librarian" } }

    // src/Librarian.Api/appsettings.Development.json
    { "Urls": "http://127.0.0.1:5080",
      "ConnectionStrings": { "Postgres": "Host=127.0.0.1;Port=5432;Database=librarian;Username=librarian;Password=librarian" } }

    // src/Librarian.Evals/appsettings.Development.json
    { "Mistral": { "ApiKey": "..." },
      "ConnectionStrings": { "Postgres": "Host=127.0.0.1;Port=5432;Database=librarian;Username=librarian;Password=librarian" },
      "Evals": { "Root": "/home/USER/.local/share/librarian-dotnet-dev/evals-dotnet" } }

`Properties/launchSettings.json` sets the environment for `dotnet run`. From `dotnet/`:

    dotnet run --project src/Librarian.Api       # http://127.0.0.1:5080/health
    dotnet run --project src/Librarian.Ingest    # logs a scan tick every 30 s

In the dev compose the apps run too (`ingest` and `api` in `infra/compose.yaml`): the thin dev
image (`dotnet/Dockerfile.dev`) carries no compiled app — the host's build output
(`src/<Host>/bin/Debug/net10.0`) is bind-mounted over `/app`, together with the app's own config
files (`appsettings.Development.json` among them), so a host build plus a container restart is the
whole loop, and the restarted ingest re-scans the inbox. Compose sets only the environment name
(Development) — the apps read their config from their files, never from compose. Ingest runs in
host network, so the files' `127.0.0.1` links reach the compose Postgres, docling and bge-m3, and
its dev root is mounted at the same absolute path — ingest is the only app that writes the
library. Api runs on the bridge with `127.0.0.1:5080` published: on the bridge the files'
`127.0.0.1` would point at the app itself, so its listen address and connection string come from
the service's `environment` (env wins over files). Paths are absolute — the app expands
no `~`.

## Build and test

VS Code tasks (`.vscode/tasks.json`) are the only control surface: `dotnet: build`, `dotnet:
test`, `dotnet: migrate`, the `librarian:evals` tasks, the `infra:` tasks (`up/stop/status/logs/
reset` include the app services), and the app tasks — `app: ingest|api restart` (recreate one
container on the already-fresh mounted output) and `app: ingest|api build+restart` (host build,
then the restart, in one task). Nothing of the Librarian runs on the host day to day: `infra: up`
brings the externals and both apps up, Api on `127.0.0.1:5080`, Ingest with no port (its health is
its log tick). From a shell with cwd `dotnet/`: `dotnet restore --locked-mode`, `dotnet build`,
`dotnet test`.

Search has no tests by design: its quality is the search eval's, measured against the dev
library — compose up, the documents ingested, the cases and runs outside the repo. Refine's
quality is its own leg: the transcripts are the case files' gold queries (count and periods
scored, the text printed for reading). From `dotnet/`:

    dotnet run --project src/Librarian.Evals -- search --mode vector|keyword [--limit N]
    dotnet run --project src/Librarian.Evals -- refine

The .NET 10 SDK lives in `~/.dotnet` on the dev machines: it must be on `PATH` with `DOTNET_ROOT`
set for the app hosts.

Migrations: EF Core in Adapters (`Postgres/Migrations/`), run as their own step, never on an app's
start — the `dotnet: migrate` task, host-side against the published `127.0.0.1:5432` (the dev
connection string comes from the gitignored overlay). From `dotnet/`:

    cd dotnet
    DOTNET_ENVIRONMENT=Development dotnet ef database update \
      --project src/Librarian.Adapters --startup-project src/Librarian.Ingest \
      --connection "Host=127.0.0.1;Port=5432;Database=librarian;Username=librarian;Password=librarian"

Deploy runs the migrations bundle as its own step, as the owner login. Roles, grants, extensions:
SQL in `infra/postgres/` (`vector` and `unaccent` come from there, not from a migration).

## Branches

Work branches off `develop`, one PR per task, local only until the cutover (see `CLAUDE.md`).
