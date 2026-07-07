"""create library import jobs settings

Revision ID: 0002_foundation
Revises: 0001_create_users
Create Date: 2026-07-07 00:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_foundation"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


settings_table = sa.table(
    "settings",
    sa.column("key", sa.String(length=120)),
    sa.column("value", sa.String(length=500)),
    sa.column("description", sa.String(length=240)),
)


def upgrade() -> None:
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("description", sa.String(length=240), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("key", name="uq_settings_key"),
    )
    op.create_index("ix_settings_key", "settings", ["key"])

    op.create_table(
        "import_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("pending_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_requests_content_type", "import_requests", ["content_type"])
    op.create_index("ix_import_requests_pending_delete", "import_requests", ["pending_delete"])
    op.create_index("ix_import_requests_source_type", "import_requests", ["source_type"])
    op.create_index("ix_import_requests_status", "import_requests", ["status"])

    op.create_table(
        "library_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source_import_id", sa.Integer(), sa.ForeignKey("import_requests.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_library_items_content_type", "library_items", ["content_type"])
    op.create_index("ix_library_items_status", "library_items", ["status"])
    op.create_index("ix_library_items_title", "library_items", ["title"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("pending_delete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("progress_message", sa.String(length=240), nullable=False),
        sa.Column("error_summary", sa.String(length=240), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("related_library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=True),
        sa.Column("related_import_id", sa.Integer(), sa.ForeignKey("import_requests.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_pending_delete", "jobs", ["pending_delete"])
    op.create_index("ix_jobs_type", "jobs", ["type"])

    op.bulk_insert(
        settings_table,
        [
            {
                "key": "target_duration_hours",
                "value": "4.9",
                "description": "Default target duration per Yoto MYO card.",
            },
            {
                "key": "target_size_mb",
                "value": "480",
                "description": "Default target size per Yoto MYO card.",
            },
            {
                "key": "normalise_loudness_default",
                "value": "true",
                "description": "Whether loudness normalisation is enabled by default.",
            },
            {
                "key": "audiobook_bitrate_kbps",
                "value": "96",
                "description": "Default spoken-word bitrate.",
            },
            {
                "key": "music_bitrate_kbps",
                "value": "128",
                "description": "Default music bitrate.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_type", table_name="jobs")
    op.drop_index("ix_jobs_pending_delete", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_library_items_title", table_name="library_items")
    op.drop_index("ix_library_items_status", table_name="library_items")
    op.drop_index("ix_library_items_content_type", table_name="library_items")
    op.drop_table("library_items")
    op.drop_index("ix_import_requests_status", table_name="import_requests")
    op.drop_index("ix_import_requests_source_type", table_name="import_requests")
    op.drop_index("ix_import_requests_pending_delete", table_name="import_requests")
    op.drop_index("ix_import_requests_content_type", table_name="import_requests")
    op.drop_table("import_requests")
    op.drop_index("ix_settings_key", table_name="settings")
    op.drop_table("settings")
