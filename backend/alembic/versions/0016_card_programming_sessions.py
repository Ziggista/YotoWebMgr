"""create card programming sessions

Revision ID: 0016_card_programming_sessions
Revises: 0015_card_programming_events
Create Date: 2026-07-19 00:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0016_card_programming_sessions"
down_revision: Union[str, None] = "0015_card_programming_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_programming_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_key", sa.String(length=80), nullable=False),
        sa.Column("active_card_id", sa.Integer(), sa.ForeignKey("physical_cards.id"), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("target_label", sa.String(length=240), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=True),
        sa.Column("playlist_draft_id", sa.Integer(), sa.ForeignKey("yoto_playlist_drafts.id"), nullable=True),
        sa.Column("playlist_uri", sa.String(length=500), nullable=True),
        sa.Column("programmable_id", sa.String(length=160), nullable=True),
        sa.Column("ndef_payload_text", sa.Text(), nullable=True),
        sa.Column("ndef_payload_hex", sa.Text(), nullable=True),
        sa.Column("source_scan_dump_id", sa.Integer(), sa.ForeignKey("card_scan_dumps.id"), nullable=True),
        sa.Column("verification_armed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "last_verification_event_id",
            sa.Integer(),
            sa.ForeignKey("card_programming_events.id"),
            nullable=True,
        ),
        sa.Column("extra_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_card_programming_sessions_session_key", "card_programming_sessions", ["session_key"], unique=True)
    op.create_index("ix_card_programming_sessions_active_card_id", "card_programming_sessions", ["active_card_id"])
    op.create_index("ix_card_programming_sessions_source", "card_programming_sessions", ["source"])
    op.create_index("ix_card_programming_sessions_library_item_id", "card_programming_sessions", ["library_item_id"])
    op.create_index("ix_card_programming_sessions_playlist_draft_id", "card_programming_sessions", ["playlist_draft_id"])
    op.create_index("ix_card_programming_sessions_source_scan_dump_id", "card_programming_sessions", ["source_scan_dump_id"])
    op.create_index(
        "ix_card_programming_sessions_last_verification_event_id",
        "card_programming_sessions",
        ["last_verification_event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_card_programming_sessions_last_verification_event_id", table_name="card_programming_sessions")
    op.drop_index("ix_card_programming_sessions_source_scan_dump_id", table_name="card_programming_sessions")
    op.drop_index("ix_card_programming_sessions_playlist_draft_id", table_name="card_programming_sessions")
    op.drop_index("ix_card_programming_sessions_library_item_id", table_name="card_programming_sessions")
    op.drop_index("ix_card_programming_sessions_source", table_name="card_programming_sessions")
    op.drop_index("ix_card_programming_sessions_active_card_id", table_name="card_programming_sessions")
    op.drop_index("ix_card_programming_sessions_session_key", table_name="card_programming_sessions")
    op.drop_table("card_programming_sessions")
