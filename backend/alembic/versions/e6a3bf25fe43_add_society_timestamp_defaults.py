from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6a3bf25fe43"
down_revision: Union[str, Sequence[str], None] = "46110a3152dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "societies",
        "created_at",
        server_default=sa.text("now()"),
    )

    op.alter_column(
        "societies",
        "updated_at",
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.alter_column(
        "societies",
        "created_at",
        server_default=None,
    )

    op.alter_column(
        "societies",
        "updated_at",
        server_default=None,
    )