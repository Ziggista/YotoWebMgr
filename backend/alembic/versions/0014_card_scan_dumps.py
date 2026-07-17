"""create card scan dumps

Revision ID: 0014_card_scan_dumps
Revises: 0013_card_scan_metadata
Create Date: 2026-07-17 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0014_card_scan_dumps"
down_revision: Union[str, None] = "0013_card_scan_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_scan_dumps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scan_source", sa.String(length=80), nullable=False),
        sa.Column("runtime", sa.String(length=120), nullable=True),
        sa.Column("programmable_id", sa.String(length=160), nullable=True),
        sa.Column("nfc_serial_number", sa.String(length=160), nullable=True),
        sa.Column("ndef_payload_text", sa.Text(), nullable=True),
        sa.Column("ndef_payload_hex", sa.Text(), nullable=True),
        sa.Column("tag_info", sa.JSON(), nullable=True),
        sa.Column("records", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_card_scan_dumps_created_at", "card_scan_dumps", ["created_at"])
    op.create_index("ix_card_scan_dumps_scan_source", "card_scan_dumps", ["scan_source"])
    op.create_index("ix_card_scan_dumps_programmable_id", "card_scan_dumps", ["programmable_id"])
    op.create_index("ix_card_scan_dumps_nfc_serial_number", "card_scan_dumps", ["nfc_serial_number"])


def downgrade() -> None:
    op.drop_index("ix_card_scan_dumps_nfc_serial_number", table_name="card_scan_dumps")
    op.drop_index("ix_card_scan_dumps_programmable_id", table_name="card_scan_dumps")
    op.drop_index("ix_card_scan_dumps_scan_source", table_name="card_scan_dumps")
    op.drop_index("ix_card_scan_dumps_created_at", table_name="card_scan_dumps")
    op.drop_table("card_scan_dumps")
