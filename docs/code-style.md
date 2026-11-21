# Code style

Where things belong and how they are shaped. One rule per line, no rationale here: the names,
tests and this file are the contract. Build, packages and config: [architecture.md](architecture.md).

## Projects and the direction

- `Librarian.Application`: the logic and its ports. References nothing.
- `Librarian.Adapters`: one implementation per technology, adapting to the ports. → Application.
- `Librarian.Ingest`, `Librarian.Api`: the host programs. → Application and Adapters.
- `tests/Librarian.Tests`: mirrors the code; references everything.
- Application's isolation is enforced by a test that fails on any `ProjectReference`,
  `Librarian.*` assembly reference, or database package.

## Application

- `Ports/{Feature}/`: every port the app declares, one interface per file, each interface carrying
  its own models in the same file (`Ports/Ingest/IDocumentReader.cs` holds the interface and its
  `Page`). Ports are named by role, never by vendor: `IDocumentReader`, not `IMistralOcr`.
- `Handlers/{Feature}/`: the verticals, the brain — one directory is one feature
  (`Handlers/Ingest/`), holding `Handler.cs` (the flow), `Options.cs` (the config sections it
  loads, validated before anything runs) and a step that grows gets a subfolder
  (`Handlers/Ingest/Extract/`). A `Validator.cs` appears only when the feature needs one.
- `Services/`: application-level services shared across features, so logic is neither duplicated
  nor spread. It appears when the first such service exists — no folder ahead of its need.
- The application handler is the flow: a command/its handler in the mediator style, plain C#,
  no mediator package. The host calls it through its interface.
- Options: one class per config section, `Validate()` called before anything runs. No defaults in
  an options class: a value the config does not set fails at start, named by its key — an unset
  option is never silently a literal. What is identical everywhere lives in `appsettings.json`;
  machine paths and secrets only in the overlaid machine settings or environment.
- Facts kept as data, not code: a catalog is an embedded JSON resource next to the feature, read
  by a small loader class. A name is added by editing the file.
- Results are immutable records. One shared `JsonSerializerOptions` per vertical, source-generated
  (`[JsonSourceGenerationOptions]` context); a converter the AOT check rejects is
  `JsonStringEnumConverter<T>`, never the non-generic one.
- A check that decides a stored flag (`verified`) is code, never the model. The model's own claim
  of correctness is never trusted.

## Adapters

- One directory per technology: `Docling/`, `Mistral/`, `FileSystem/`, `Postgres/`.
- An adapter implements a port and returns only Application types. Vendor and wire types never
  cross the boundary; they stay inside the adapter file they were made in.
- `HttpClient`s come from `IHttpClientFactory`, named by role (`"doclingReader"`, `"ocrReader"`), one typed
  client per service. No vendor SDK where a plain HTTP call works.
- Resilience handler settings are always explicit: attempt and total timeout both set (the
  default 10 s attempt timeout kills slow readers), and the circuit breaker's sampling duration
  at least double the attempt timeout (options validation refuses less).
- A paid API gets a budget gate before the call and retries nothing: a retry is another paid call.
- Multiple implementations of one port register keyed (`"doclingReader"`, `"ocrReader"`); all
  registrations live in the project's
  `DependencyInjectionExtensions` (`AddLibrarian<Capability>`), one place.

## Agents

- One factory method builds an agent (`MistralAgentFactory.Create`): the client with its options
  (`Endpoint`, `RetryPolicy = new ClientRetryPolicy(3)`, `UserAgentApplicationId`, a transport),
  the pipeline (the tool loop, capped in config), the instructions resource, the telemetry wrap —
  all in one place, all adapter work. The rules an agent runs
  (checks, catalogs, message building) are Application's.
- An agent is a keyed singleton holding only what is fixed: its instructions, its pipeline, its
  `IChatClient`. Singletons never hold run data.
- Run-only context rides run-only tools: the handler asks a port for this run's options
  (`IExtractRunOptionsFactory`), the adapter closes the document's text inside the tool
  (captured, not a parameter, so the model sees an unchanged schema) and passes them in the run
  options — MAF merges run options over the agent's fixed ones: instructions stay, a run's tools
  travel; pinned by a test. No ambient state, no `AsyncLocal`. Anything per run travels in the
  run.
- Fixed instructions are an embedded `.md` resource under the vendor's `Instructions/` folder,
  one file per agent (`Instructions/extract.md`); what varies per run goes in the run's message,
  never in the instructions.
- Model and endpoint come from config, so a test or eval builds the same agent over another
  `IChatClient` without touching logic.
- The tool loop is capped in config. Structured output (`RunAsync<T>`) parses strictly; a parse
  failure is fed back on the same session and retried, capped — our code, below the framework.
- A model answering with thinking is a wire problem before it is a logic problem: Mistral's
  thinking content parts crash the stock OpenAI client, so the `ThinkingShim` strips them at the
  `HttpClient` transport, under the client, before the SDK reads a byte. A new vendor quirk on the
  reply lands next to it, as a handler on the same transport.

## Hosts

- `Program.cs` stays bare: create the builder, one `Add<Host>Services(configuration)` call, run.
- All registrations live in `ProgramExtensions` as `Add<Host>Services`, composed of private
  `Add<Layer>` methods (`AddOptions`, `AddTracing`, `AddDb`), one concern per method.
- `Librarian.Api` is composed of features: `Features/<Feature>/` with `Request.cs`, `Response.cs`
  (both as they exist) and the endpoint mapping, minimal APIs.
- A `BackgroundService` decides nothing about the work. It finds candidates (files, timers) and
  hands the application handler what it found.
- A host loop survives a failing item: each item is taken inside its own try/catch, the error is
  logged, the tick continues. A poison item is retried until the store can bank it as a failed
  document; banking is the store's business (05), not the loop's.

## Tests

- One folder per vertical (`Ingest/`), mirroring the code's names.
- Logic is tested pure; an adapter is proved against the real service, config-borne paths only
  (the repo never names a data path).
- `TestContext.Current.CancellationToken` everywhere a token is taken; the xUnit analyzers run as
  errors.

## Names

- An object's name ends with what it does: `doclingReader`, `ocrReader`, `extractAgent`,
  `messageBuilder`, `fileStore`. A bare technology (`docling`) or a bare step (`extract`) never
  names an object — the noun says what it is.
- Keys follow the same rule and repeat one word everywhere they name the same object: the DI key,
  the `HttpClient` name and the variable are all `doclingReader`.

## Defensive

- Fail loudly at the boundaries: config in, service answers, ports. Unexpected state throws and
  the message names what is missing; nothing is silently defaulted, retried or guessed.
  Inside a validated boundary, the code trusts its inputs and stays flat.
- The bang operator (`!`) only where there is no way out — an invariant the compiler cannot see
  (a value proven behind a `Try*` check, something set inside a lambda). Prefer restructuring over
  asserting non-null.
- The one sanctioned bang is the options pattern: values arrive from the binder after
  construction, `Validate()` at start is the invariant that makes them non-null.

## Simple

- One obvious way to do the thing. Fewer wraps, fewer abstractions, fewer names.
- A class earns its place by being a port, an adapter, a host piece or a test — nothing ahead of
  its need, no folder for the future.

## Comments

- None, in any shape or form: no `//`, no `///`, no XML doc, none. Code that needs prose goes to
  the docs or a test name instead.
