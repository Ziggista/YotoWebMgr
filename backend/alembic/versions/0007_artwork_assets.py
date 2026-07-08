"""create artwork assets

Revision ID: 0007_artwork_assets
Revises: 0006_yoto_playlist_drafts
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_artwork_assets"
down_revision: Union[str, None] = "0006_yoto_playlist_drafts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "artwork_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("source_artwork_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False, server_default="available"),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("output_path", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("palette", sa.String(length=80), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_artwork_assets_library_item_id", "artwork_assets", ["library_item_id"])
    op.create_index("ix_artwork_assets_source_artwork_id", "artwork_assets", ["source_artwork_id"])
    op.create_index("ix_artwork_assets_kind", "artwork_assets", ["kind"])
    op.create_index("ix_artwork_assets_status", "artwork_assets", ["status"])
    op.create_index("ix_artwork_assets_checksum_sha256", "artwork_assets", ["checksum_sha256"])


def downgrade() -> None:
    op.drop_index("ix_artwork_assets_checksum_sha256", table_name="artwork_assets")
    op.drop_index("ix_artwork_assets_status", table_name="artwork_assets")
    op.drop_index("ix_artwork_assets_kind", table_name="artwork_assets")
    op.drop_index("ix_artwork_assets_source_artwork_id", table_name="artwork_assets")
    op.drop_index("ix_artwork_assets_library_item_id", table_name="artwork_assets")
    op.drop_table("artwork_assets")
