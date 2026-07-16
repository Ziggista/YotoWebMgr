"""add card scan metadata

Revision ID: 0013_card_scan_metadata
Revises: 0012_import_review_fields
Create Date: 2026-07-16 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_card_scan_metadata"
down_revision: Union[str, None] = "0012_import_review_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("physical_cards", sa.Column("nfc_serial_number", sa.String(length=160), nullable=True))
    op.add_column("physical_cards", sa.Column("ndef_payload_text", sa.Text(), nullable=True))
    op.add_column("physical_cards", sa.Column("ndef_payload_hex", sa.Text(), nullable=True))
    op.add_column("physical_cards", sa.Column("scan_source", sa.String(length=80), nullable=True))
    op.add_column("physical_cards", sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_physical_cards_nfc_serial_number", "physical_cards", ["nfc_serial_number"])


def downgrade() -> None:
    op.drop_index("ix_physical_cards_nfc_serial_number", table_name="physical_cards")
    op.drop_column("physical_cards", "last_scanned_at")
    op.drop_column("physical_cards", "scan_source")
    op.drop_column("physical_cards", "ndef_payload_hex")
    op.drop_column("physical_cards", "ndef_payload_text")
    op.drop_column("physical_cards", "nfc_serial_number")
