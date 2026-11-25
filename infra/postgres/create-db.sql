-- The library's database, owned by the main login and locked to it (the reader gets its
-- own CONNECT in create-reader.sql). Run as the Postgres superuser, against any database
-- but the one being created.
SELECT format('CREATE DATABASE librarian OWNER librarian')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'librarian')\gexec
REVOKE CONNECT, TEMPORARY ON DATABASE librarian FROM PUBLIC;
GRANT CONNECT ON DATABASE librarian TO librarian;
