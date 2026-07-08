"""create version events

Revision ID: 0003_version_events
Revises: 0002_foundation
Create Date: 2026-07-08 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_version_events"
down_revision: Union[str, None] = "0002_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "version_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entity_type", "entity_id", "version_number", name="uq_version_events_entity_version"),
    )
    op.create_index("ix_version_events_entity_type", "version_events", ["entity_type"])
    op.create_index("ix_version_events_entity_id", "version_events", ["entity_id"])
    op.create_index("ix_version_events_event_type", "version_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_version_events_event_type", table_name="version_events")
    op.drop_index("ix_version_events_entity_id", table_name="version_events")
    op.drop_index("ix_version_events_entity_type", table_name="version_events")
    op.drop_table("version_events")
