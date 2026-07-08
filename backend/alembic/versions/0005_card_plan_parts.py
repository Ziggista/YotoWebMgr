"""create saved card plan parts

Revision ID: 0005_card_plan_parts
Revises: 0004_processed_assets
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_card_plan_parts"
down_revision: Union[str, None] = "0004_processed_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_plan_parts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("estimated_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_size_mb", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_card_plan_parts_library_item_id", "card_plan_parts", ["library_item_id"])
    op.create_index("ix_card_plan_parts_part_number", "card_plan_parts", ["part_number"])

    op.create_table(
        "card_plan_track_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_plan_part_id", sa.Integer(), sa.ForeignKey("card_plan_parts.id"), nullable=False),
        sa.Column("playlist_track_id", sa.Integer(), sa.ForeignKey("playlist_tracks.id"), nullable=False),
        sa.Column("track_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_card_plan_track_assignments_card_plan_part_id",
        "card_plan_track_assignments",
        ["card_plan_part_id"],
    )
    op.create_index(
        "ix_card_plan_track_assignments_playlist_track_id",
        "card_plan_track_assignments",
        ["playlist_track_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_card_plan_track_assignments_playlist_track_id", table_name="card_plan_track_assignments")
    op.drop_index("ix_card_plan_track_assignments_card_plan_part_id", table_name="card_plan_track_assignments")
    op.drop_table("card_plan_track_assignments")
    op.drop_index("ix_card_plan_parts_part_number", table_name="card_plan_parts")
    op.drop_index("ix_card_plan_parts_library_item_id", table_name="card_plan_parts")
    op.drop_table("card_plan_parts")
