from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "87cec332e103"
down_revision: str | Sequence[str] | None = "0bf88b91927d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asks",
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("question", sa.String(), nullable=False),
        sa.Column("agent_model", sa.String(), nullable=False),
        sa.Column("refine_model", sa.String(), nullable=False),
        sa.Column("reasoning", sa.String(), nullable=False),
        sa.Column("prompt", sa.String(), nullable=False),
        sa.Column("git_sha", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("found", "partial", "not_found", "error", name="status", native_enum=False),
            nullable=True,
        ),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("rounds", sa.Integer(), nullable=True),
        sa.Column("calls", sa.Integer(), nullable=True),
        sa.Column("ms", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('found', 'partial', 'not_found', 'error')",
            name=op.f("ck_asks_status"),
        ),
        sa.PrimaryKeyConstraint("correlation_id", name=op.f("pk_asks")),
    )
    op.create_table(
        "ask_events",
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("step", sa.String(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["correlation_id"],
            ["asks.correlation_id"],
            name=op.f("fk_ask_events_correlation_id_asks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("correlation_id", "seq", name=op.f("pk_ask_events")),
    )
    op.create_table(
        "ask_feedback",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("correlation_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("value", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["correlation_id"],
            ["asks.correlation_id"],
            name=op.f("fk_ask_feedback_correlation_id_asks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ask_feedback")),
    )


def downgrade() -> None:
    op.drop_table("ask_feedback")
    op.drop_table("ask_events")
    op.drop_table("asks")
