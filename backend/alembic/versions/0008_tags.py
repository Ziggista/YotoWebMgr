"""create reusable tags

Revision ID: 0008_tags
Revises: 0007_artwork_assets
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_tags"
down_revision: Union[str, None] = "0007_artwork_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


tags_table = sa.table(
    "tags",
    sa.column("name", sa.String(length=120)),
    sa.column("normalized_name", sa.String(length=120)),
    sa.column("color", sa.String(length=40)),
)


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),
    )
    op.create_index("ix_tags_normalized_name", "tags", ["normalized_name"])

    op.create_table(
        "tag_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id"), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tag_id", "entity_type", "entity_id", name="uq_tag_assignments_entity"),
    )
    op.create_index("ix_tag_assignments_tag_id", "tag_assignments", ["tag_id"])
    op.create_index("ix_tag_assignments_entity_type", "tag_assignments", ["entity_type"])
    op.create_index("ix_tag_assignments_entity_id", "tag_assignments", ["entity_id"])

    op.bulk_insert(
        tags_table,
        [
            {"name": "Krystin", "normalized_name": "krystin", "color": "#f6ad55"},
            {"name": "Dale", "normalized_name": "dale", "color": "#63b3ed"},
            {"name": "Elyza", "normalized_name": "elyza", "color": "#f687b3"},
            {"name": "Family", "normalized_name": "family", "color": "#68d391"},
            {"name": "Audiobook", "normalized_name": "audiobook", "color": "#b794f4"},
            {"name": "Music", "normalized_name": "music", "color": "#4fd1c5"},
            {"name": "Story Collection", "normalized_name": "story collection", "color": "#fbd38d"},
            {"name": "Bedtime", "normalized_name": "bedtime", "color": "#90cdf4"},
            {"name": "Car Trip", "normalized_name": "car trip", "color": "#fbb6ce"},
            {"name": "Educational", "normalized_name": "educational", "color": "#9ae6b4"},
            {"name": "Favourite", "normalized_name": "favourite", "color": "#fc8181"},
            {"name": "Calm", "normalized_name": "calm", "color": "#81e6d9"},
            {"name": "Christmas", "normalized_name": "christmas", "color": "#f56565"},
            {"name": "School Holidays", "normalized_name": "school holidays", "color": "#d6bcfa"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_tag_assignments_entity_id", table_name="tag_assignments")
    op.drop_index("ix_tag_assignments_entity_type", table_name="tag_assignments")
    op.drop_index("ix_tag_assignments_tag_id", table_name="tag_assignments")
    op.drop_table("tag_assignments")
    op.drop_index("ix_tags_normalized_name", table_name="tags")
    op.drop_table("tags")
