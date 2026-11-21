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
├── src/
│   ├── Librarian.Application  the brain: Ports/{Feature}/, Handlers/{Feature}/,
│   │                          Services/ when the first shared service exists;
│   │                          references nothing (a test enforces it)
│   ├── Librarian.Adapters     one directory per technology (Docling/, Mistral/,
│   │                          FileSystem/, Postgres/); → Application
│   ├── Librarian.Ingest       worker host, scans the inbox on a timer; → Application, Adapters
│   └── Librarian.Api          ASP.NET Core host; → Application, Adapters
└── tests/Librarian.Tests      xUnit v3
```

References point one way: hosts → Application and Adapters; Adapters → Application. Two programs,
each its own container at deploy: only Ingest gets the inbox mounted; Api cannot write to the library.

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

Each program reads `appsettings.json` (only what is identical in every environment), then
`appsettings.{Environment}.json`, then environment variables (`__` is `:`; env wins). No `.env`
files. The dev overlay `appsettings.Development.json` is gitignored (it holds an absolute machine
path); its keys:

    // src/Librarian.Ingest/appsettings.Development.json
    { "Librarian": { "Root": "/home/USER/.local/share/librarian-dotnet-dev" },
      "Mistral": { "ApiKey": "..." } }

    // src/Librarian.Api/appsettings.Development.json
    { "Urls": "http://127.0.0.1:5080",
      "ConnectionStrings": { "Postgres": "Host=127.0.0.1;Port=5432;Database=librarian;Username=librarian;Password=librarian" } }

`Properties/launchSettings.json` sets the environment for `dotnet run`. From `dotnet/`:

    dotnet run --project src/Librarian.Api       # http://127.0.0.1:5080/health
    dotnet run --project src/Librarian.Ingest    # logs a scan tick every 30 s

In containers the same keys arrive as real environment variables; compose binds only the inbox
directory. Paths are absolute — the app expands no `~`.

## Build and test

VS Code tasks (`.vscode/tasks.json`): `dotnet: build`, `dotnet: test`, plus the `infra:` tasks.
From a shell with cwd `dotnet/`: `dotnet restore --locked-mode`, `dotnet build`, `dotnet test`.
The .NET 10 SDK lives in `~/.dotnet` on the dev machines: it must be on `PATH` with `DOTNET_ROOT`
set for the app hosts.

Migrations: EF Core in Adapters, run as their own step (a migrations bundle, owner login), never
on an app's start. Roles, grants, extensions: SQL in `infra/postgres/`.

## Branches

Work branches off `develop`, one PR per task, local only until the cutover (see `CLAUDE.md`).
