"""create card assignment events

Revision ID: 0009_card_assignment_events
Revises: 0008_tags
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0009_card_assignment_events"
down_revision: Union[str, None] = "0008_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_assignment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("physical_cards.id"), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("previous_library_item_id", sa.Integer(), nullable=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("previous_status", sa.String(length=80), nullable=True),
        sa.Column("new_status", sa.String(length=80), nullable=True),
        sa.Column("previous_yoto_playlist_uri", sa.String(length=500), nullable=True),
        sa.Column("yoto_playlist_uri", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_card_assignment_events_card_id", "card_assignment_events", ["card_id"])
    op.create_index("ix_card_assignment_events_event_type", "card_assignment_events", ["event_type"])
    op.create_index("ix_card_assignment_events_library_item_id", "card_assignment_events", ["library_item_id"])
    op.create_index("ix_card_assignment_events_job_id", "card_assignment_events", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_card_assignment_events_job_id", table_name="card_assignment_events")
    op.drop_index("ix_card_assignment_events_library_item_id", table_name="card_assignment_events")
    op.drop_index("ix_card_assignment_events_event_type", table_name="card_assignment_events")
    op.drop_index("ix_card_assignment_events_card_id", table_name="card_assignment_events")
    op.drop_table("card_assignment_events")
