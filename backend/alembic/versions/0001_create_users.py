"""create users

Revision ID: 0001_create_users
Revises:
Create Date: 2026-07-07 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_create_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


users_table = sa.table(
    "users",
    sa.column("slug", sa.String(length=64)),
    sa.column("display_name", sa.String(length=120)),
    sa.column("username", sa.String(length=120)),
    sa.column("password_hash", sa.String(length=255)),
    sa.column("is_household_admin", sa.Boolean()),
    sa.column("can_quick_select", sa.Boolean()),
)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("is_household_admin", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("can_quick_select", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_users_slug"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_slug", "users", ["slug"])
    op.create_index("ix_users_username", "users", ["username"])

    op.bulk_insert(
        users_table,
        [
            {
                "slug": "krystin",
                "display_name": "Krystin",
                "username": "krystin",
                "password_hash": None,
                "is_household_admin": True,
                "can_quick_select": True,
            },
            {
                "slug": "dale",
                "display_name": "Dale",
                "username": "dale",
                "password_hash": None,
                "is_household_admin": True,
                "can_quick_select": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_slug", table_name="users")
    op.drop_table("users")
