"""add card programming session states

Revision ID: 0017_card_programming_session_states
Revises: 0016_card_programming_sessions
Create Date: 2026-07-19 01:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0017_card_programming_session_states"
down_revision: Union[str, None] = "0016_card_programming_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "card_programming_sessions",
        sa.Column("write_state", sa.String(length=80), nullable=False, server_default="idle"),
    )
    op.add_column(
        "card_programming_sessions",
        sa.Column("written_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "card_programming_sessions",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_card_programming_sessions_write_state", "card_programming_sessions", ["write_state"])


def downgrade() -> None:
    op.drop_index("ix_card_programming_sessions_write_state", table_name="card_programming_sessions")
    op.drop_column("card_programming_sessions", "verified_at")
    op.drop_column("card_programming_sessions", "written_at")
    op.drop_column("card_programming_sessions", "write_state")
