"""create yoto playlist versions

Revision ID: 0011_yoto_playlist_versions
Revises: 0010_yoto_credential_states
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_yoto_playlist_versions"
down_revision: Union[str, None] = "0010_yoto_credential_states"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "yoto_playlist_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("playlist_draft_id", sa.Integer(), sa.ForeignKey("yoto_playlist_drafts.id"), nullable=False),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("source_event", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_yoto_playlist_versions_playlist_draft_id", "yoto_playlist_versions", ["playlist_draft_id"])
    op.create_index("ix_yoto_playlist_versions_library_item_id", "yoto_playlist_versions", ["library_item_id"])
    op.create_index("ix_yoto_playlist_versions_status", "yoto_playlist_versions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_yoto_playlist_versions_status", table_name="yoto_playlist_versions")
    op.drop_index("ix_yoto_playlist_versions_library_item_id", table_name="yoto_playlist_versions")
    op.drop_index("ix_yoto_playlist_versions_playlist_draft_id", table_name="yoto_playlist_versions")
    op.drop_table("yoto_playlist_versions")
