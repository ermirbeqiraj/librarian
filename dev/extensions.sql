-- Dev only: the compose Postgres runs this once, on an empty volume, as its superuser.
-- No migration creates extensions; on the homeserver the DBA creates them by hand.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
