"""create processed assets

Revision ID: 0004_processed_assets
Revises: 0003_version_events
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_processed_assets"
down_revision: Union[str, None] = "0003_version_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("playlist_tracks", sa.Column("source_start_seconds", sa.Integer(), nullable=True))
    op.add_column("playlist_tracks", sa.Column("source_end_seconds", sa.Integer(), nullable=True))

    op.create_table(
        "processed_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("playlist_track_id", sa.Integer(), sa.ForeignKey("playlist_tracks.id"), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("output_path", sa.Text(), nullable=False),
        sa.Column("codec", sa.String(length=80), nullable=False),
        sa.Column("bitrate_kbps", sa.Integer(), nullable=False),
        sa.Column("channels", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("profile", sa.String(length=80), nullable=False),
        sa.Column("settings_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_processed_assets_library_item_id", "processed_assets", ["library_item_id"])
    op.create_index("ix_processed_assets_playlist_track_id", "processed_assets", ["playlist_track_id"])
    op.create_index("ix_processed_assets_checksum_sha256", "processed_assets", ["checksum_sha256"])


def downgrade() -> None:
    op.drop_index("ix_processed_assets_checksum_sha256", table_name="processed_assets")
    op.drop_index("ix_processed_assets_playlist_track_id", table_name="processed_assets")
    op.drop_index("ix_processed_assets_library_item_id", table_name="processed_assets")
    op.drop_table("processed_assets")
    op.drop_column("playlist_tracks", "source_end_seconds")
    op.drop_column("playlist_tracks", "source_start_seconds")
