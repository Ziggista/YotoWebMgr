"""create yoto credential states

Revision ID: 0010_yoto_credential_states
Revises: 0009_card_assignment_events
Create Date: 2026-07-09 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_yoto_credential_states"
down_revision: Union[str, None] = "0009_card_assignment_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "yoto_credential_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_label", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("token_storage_ref", sa.String(length=240), nullable=True),
        sa.Column("masked_account_id", sa.String(length=240), nullable=True),
        sa.Column("masked_email", sa.String(length=240), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("authorization_url", sa.Text(), nullable=True),
        sa.Column("oauth_state", sa.String(length=240), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_yoto_credential_states_status", "yoto_credential_states", ["status"])
    op.create_index("ix_yoto_credential_states_oauth_state", "yoto_credential_states", ["oauth_state"])


def downgrade() -> None:
    op.drop_index("ix_yoto_credential_states_oauth_state", table_name="yoto_credential_states")
    op.drop_index("ix_yoto_credential_states_status", table_name="yoto_credential_states")
    op.drop_table("yoto_credential_states")
