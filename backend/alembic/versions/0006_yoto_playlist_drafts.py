"""create yoto playlist drafts

Revision ID: 0006_yoto_playlist_drafts
Revises: 0005_card_plan_parts
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_yoto_playlist_drafts"
down_revision: Union[str, None] = "0005_card_plan_parts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "yoto_playlist_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("related_job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="draft"),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("remote_playlist_id", sa.String(length=240), nullable=True),
        sa.Column("remote_playlist_uri", sa.String(length=500), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_yoto_playlist_drafts_library_item_id", "yoto_playlist_drafts", ["library_item_id"])
    op.create_index("ix_yoto_playlist_drafts_related_job_id", "yoto_playlist_drafts", ["related_job_id"])
    op.create_index("ix_yoto_playlist_drafts_status", "yoto_playlist_drafts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_yoto_playlist_drafts_status", table_name="yoto_playlist_drafts")
    op.drop_index("ix_yoto_playlist_drafts_related_job_id", table_name="yoto_playlist_drafts")
    op.drop_index("ix_yoto_playlist_drafts_library_item_id", table_name="yoto_playlist_drafts")
    op.drop_table("yoto_playlist_drafts")
