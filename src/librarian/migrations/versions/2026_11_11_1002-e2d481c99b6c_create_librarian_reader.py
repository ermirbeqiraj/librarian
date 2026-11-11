from collections.abc import Sequence

from alembic import op

from librarian.config import READER_PASSWORD

revision: str = "e2d481c99b6c"
down_revision: str | Sequence[str] | None = "0bf88b91927d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The role is cluster-wide, so it is created once no matter which database is
    # migrated (librarian, librarian_test); the grants below are per database. The
    # password comes from the environment, never from this file.
    password = READER_PASSWORD.replace("'", "''")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'librarian_reader') THEN
                CREATE ROLE librarian_reader LOGIN PASSWORD '{password}';
            ELSE
                ALTER ROLE librarian_reader PASSWORD '{password}';
            END IF;
        END $$;
        """
    )
    # The SQL tool's borders: every transaction read-only and nothing to escape back
    # to, 5 s per statement, SELECT on documents and document_sections only.
    op.execute("ALTER ROLE librarian_reader SET default_transaction_read_only = on")
    op.execute("ALTER ROLE librarian_reader SET statement_timeout = '5s'")
    op.execute("GRANT USAGE ON SCHEMA public TO librarian_reader")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM librarian_reader")
    op.execute("GRANT SELECT ON documents, document_sections TO librarian_reader")


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM librarian_reader")
    op.execute("DROP OWNED BY librarian_reader")
    op.execute("DROP ROLE IF EXISTS librarian_reader")
