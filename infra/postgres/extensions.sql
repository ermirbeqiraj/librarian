-- No migration creates extensions.
-- Dev: the compose Postgres runs this once, on an empty volume, as its superuser
-- (the docker-entrypoint-initdb.d mount in infra/compose.yaml).
-- Production: by hand on the target, connected to the librarian database —
--   docker exec -i postgres psql -U postgres -d librarian -v ON_ERROR_STOP=1 < infra/postgres/extensions.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
