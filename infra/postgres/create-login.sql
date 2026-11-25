-- The main login: owns the database, runs the migrations. Run as the Postgres superuser,
-- against any database. The password is set by hand and never enters a file:
--   \password librarian
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'librarian') THEN
        CREATE ROLE librarian LOGIN;
    END IF;
END
$$;
