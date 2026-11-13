from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0bf88b91927d"
down_revision: str | Sequence[str] | None = "c92cd9bb80ef"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# unaccent itself is STABLE (it reads the dictionary at call time), so it cannot go into a
# generated column directly; this wrapper pins the dictionary and is immutable.
UNACCENT_IMMUTABLE = """
CREATE OR REPLACE FUNCTION unaccent_immutable(text)
RETURNS text AS $$
    SELECT public.unaccent('public.unaccent'::regdictionary, $1)
$$ LANGUAGE SQL IMMUTABLE PARALLEL SAFE STRICT
"""


def upgrade() -> None:
    # The unaccent extension is not created here: extensions are the DBA's (dev compose
    # creates it in dev/extensions.sql, the test setup in librarian_test).
    op.execute(UNACCENT_IMMUTABLE)
    op.add_column(
        "chunks",
        sa.Column(
            "search_text",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('italian', unaccent_immutable(text))", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chunks_search_text", "chunks", ["search_text"], unique=False, postgresql_using="gin"
    )
    # No vector index: the library is small enough for an exact scan.


def downgrade() -> None:
    op.drop_index("ix_chunks_search_text", table_name="chunks", postgresql_using="gin")
    op.drop_column("chunks", "search_text")
    op.execute("DROP FUNCTION IF EXISTS unaccent_immutable(text)")
