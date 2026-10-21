from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "69bc9c445609"
down_revision: str | Sequence[str] | None = "5cfe5cf2f998"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestions",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("original_file_name", sa.String(), nullable=False),
        sa.Column("destination_path", sa.String(), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum("received", "done", "duplicate", "failed", name="status", native_enum=False),
            nullable=False,
        ),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('received', 'done', 'duplicate', 'failed')",
            name=op.f("ck_ingestions_status"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestions")),
    )
    op.create_index(
        op.f("ix_ingestions_content_hash"), "ingestions", ["content_hash"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ingestions_content_hash"), table_name="ingestions")
    op.drop_table("ingestions")
