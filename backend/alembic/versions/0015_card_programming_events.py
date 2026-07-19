"""create card programming events

Revision ID: 0015_card_programming_events
Revises: 0014_card_scan_dumps
Create Date: 2026-07-19 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0015_card_programming_events"
down_revision: Union[str, None] = "0014_card_scan_dumps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_programming_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_id", sa.Integer(), sa.ForeignKey("physical_cards.id"), nullable=True),
        sa.Column("card_code", sa.String(length=80), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("runtime", sa.String(length=120), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=True),
        sa.Column("target_label", sa.String(length=240), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("compared_field", sa.String(length=80), nullable=True),
        sa.Column("matched", sa.Boolean(), nullable=True),
        sa.Column("playlist_uri", sa.String(length=500), nullable=True),
        sa.Column("programmable_id", sa.String(length=160), nullable=True),
        sa.Column("nfc_serial_number", sa.String(length=160), nullable=True),
        sa.Column("ndef_payload_text", sa.Text(), nullable=True),
        sa.Column("ndef_payload_hex", sa.Text(), nullable=True),
        sa.Column("observed_programmable_id", sa.String(length=160), nullable=True),
        sa.Column("observed_nfc_serial_number", sa.String(length=160), nullable=True),
        sa.Column("observed_ndef_payload_text", sa.Text(), nullable=True),
        sa.Column("observed_ndef_payload_hex", sa.Text(), nullable=True),
        sa.Column("extra_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_card_programming_events_card_id", "card_programming_events", ["card_id"])
    op.create_index("ix_card_programming_events_card_code", "card_programming_events", ["card_code"])
    op.create_index("ix_card_programming_events_event_type", "card_programming_events", ["event_type"])
    op.create_index("ix_card_programming_events_source", "card_programming_events", ["source"])
    op.create_index(
        "ix_card_programming_events_programmable_id",
        "card_programming_events",
        ["programmable_id"],
    )
    op.create_index(
        "ix_card_programming_events_nfc_serial_number",
        "card_programming_events",
        ["nfc_serial_number"],
    )
    op.create_index("ix_card_programming_events_created_at", "card_programming_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_card_programming_events_created_at", table_name="card_programming_events")
    op.drop_index("ix_card_programming_events_nfc_serial_number", table_name="card_programming_events")
    op.drop_index("ix_card_programming_events_programmable_id", table_name="card_programming_events")
    op.drop_index("ix_card_programming_events_source", table_name="card_programming_events")
    op.drop_index("ix_card_programming_events_event_type", table_name="card_programming_events")
    op.drop_index("ix_card_programming_events_card_code", table_name="card_programming_events")
    op.drop_index("ix_card_programming_events_card_id", table_name="card_programming_events")
    op.drop_table("card_programming_events")
