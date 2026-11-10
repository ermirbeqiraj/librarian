from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c92cd9bb80ef"
down_revision: str | Sequence[str] | None = "05131009777f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("parser", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "parser")
