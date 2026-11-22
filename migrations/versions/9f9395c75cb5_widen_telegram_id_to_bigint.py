"""widen telegram_id to bigint

Telegram user IDs already exceed 32-bit ``INTEGER`` on PostgreSQL, so the
column must be ``BIGINT``. SQLite uses batch mode to rebuild the table.

Revision ID: 9f9395c75cb5
Revises: 318b82011313
Create Date: 2026-11-21 09:14:17.459848

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f9395c75cb5"
down_revision: str | Sequence[str] | None = "318b82011313"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "telegram_id",
            existing_type=sa.Integer(),
            type_=sa.BigInteger(),
            existing_nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "telegram_id",
            existing_type=sa.BigInteger(),
            type_=sa.Integer(),
            existing_nullable=True,
        )
