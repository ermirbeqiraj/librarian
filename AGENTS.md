`dotnet/` is the app, `infra/` is the compose for the local services and the database setup.

A doc states the rules at a high level, or points at the config file, script or task that holds
the detail. No stories: it doesn't explain or restate what those files already say.

No document or personal data goes in this repo, not even in a test fixture.

The task files, evals and notes live outside this repo, because it's public. Where they are is in
`AGENTS.local.md` (not committed). If it's missing, ask before starting a task.

Branches: work branches off `develop`, one PR per task into `develop`, squash-merged. `develop` goes
to `main` only after the app's full test suite runs green against real Postgres: a DB test that
skips is untested. Each push to `main` publishes the image.
