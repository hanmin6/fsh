"""Persist complete conversation history metadata.

Revision ID: 0002_message_history
Revises: 0001_initial
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_message_history"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("history_complete", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("messages", sa.Column("source_sequence", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("source_timestamp_raw", sa.Text(), nullable=True))
    op.add_column(
        "messages", sa.Column("source_timestamp_confidence", sa.String(length=16), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("messages", "source_timestamp_confidence")
    op.drop_column("messages", "source_timestamp_raw")
    op.drop_column("messages", "source_sequence")
    op.drop_column("conversations", "history_complete")
