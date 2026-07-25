"""add remote share link url to yoto playlist drafts

Revision ID: 0018_yoto_playlist_share_links
Revises: 0017_card_programming_session_states
Create Date: 2026-07-25 22:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0018_yoto_playlist_share_links"
down_revision = "0017_programming_session_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "yoto_playlist_drafts",
        sa.Column("remote_share_link_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("yoto_playlist_drafts", "remote_share_link_url")
