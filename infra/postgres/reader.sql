-- Dev only: run as the compose superuser after the migrations, never from an app:
--   docker compose exec -T postgres psql -U librarian -d librarian < ./postgres/reader.sql
-- No migration creates roles: the ask agent's sql tool logs in as this reader, and the
-- database — not the app — enforces what it can do.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'librarian_reader') THEN
        CREATE ROLE librarian_reader LOGIN PASSWORD 'librarian_reader';
    END IF;
END
$$;

-- One statement stops after 5 seconds, in every session of the role.
ALTER ROLE librarian_reader SET statement_timeout = '5s';

-- Read-only, on the tables the ask agent can see; chunks and the app's own tables stay hidden.
GRANT USAGE ON SCHEMA public TO librarian_reader;
GRANT SELECT ON documents, fields, sections TO librarian_reader;
