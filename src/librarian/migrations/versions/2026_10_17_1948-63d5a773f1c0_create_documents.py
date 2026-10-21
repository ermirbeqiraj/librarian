from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "63d5a773f1c0"
down_revision: str | Sequence[str] | None = "69bc9c445609"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("ingestion_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("validity", postgresql.DATERANGE(), nullable=True),
        sa.Column("fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("problems", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "confirmed", name="status", native_enum=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed')",
            name=op.f("ck_documents_status"),
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_id"], ["ingestions.id"], name=op.f("fk_documents_ingestion_id_ingestions")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )
    op.create_index(
        "ix_documents_validity", "documents", ["validity"], unique=False, postgresql_using="gist"
    )


def downgrade() -> None:
    op.drop_index("ix_documents_validity", table_name="documents", postgresql_using="gist")
    op.drop_table("documents")
