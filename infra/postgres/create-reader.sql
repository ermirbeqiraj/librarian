-- The readonly login for the ask's sql tool: 5 s statement timeout, SELECT on documents,
-- fields, sections — the database, not the app, enforces it. Run as the Postgres superuser
-- after the migrations (the grants name real tables), against the librarian database.
-- The password is set by hand and never enters a file (dev fixture: librarian_reader):
--   \password librarian_reader
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'librarian_reader') THEN
        CREATE ROLE librarian_reader LOGIN;
    END IF;
END
$$;

-- One statement stops after 5 seconds, in every session of the role.
ALTER ROLE librarian_reader SET statement_timeout = '5s';

-- The database is locked to its owner (create-db.sql); the reader needs its own CONNECT.
GRANT CONNECT ON DATABASE librarian TO librarian_reader;

-- Read-only, on the tables the ask agent can see; chunks and the app's own tables stay hidden.
GRANT USAGE ON SCHEMA public TO librarian_reader;
GRANT SELECT ON documents, fields, sections TO librarian_reader;
