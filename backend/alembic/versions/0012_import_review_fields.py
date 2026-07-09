"""add import review fields

Revision ID: 0012_import_review_fields
Revises: 0011_yoto_playlist_versions
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_import_review_fields"
down_revision: Union[str, None] = "0011_yoto_playlist_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("import_requests", sa.Column("review_status", sa.String(length=64), nullable=False, server_default="needs_review"))
    op.add_column("import_requests", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("import_requests", sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("import_requests", sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("import_requests", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("import_requests", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_import_requests_review_status", "import_requests", ["review_status"])


def downgrade() -> None:
    op.drop_index("ix_import_requests_review_status", table_name="import_requests")
    op.drop_column("import_requests", "approved_at")
    op.drop_column("import_requests", "reviewed_at")
    op.drop_column("import_requests", "approved_by_user_id")
    op.drop_column("import_requests", "reviewed_by_user_id")
    op.drop_column("import_requests", "review_notes")
    op.drop_column("import_requests", "review_status")
