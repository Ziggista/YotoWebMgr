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
        sa.Column("cover_art_path", sa.Text(), nullable=True),
        sa.Column("playlist_always_play_from_start", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("playlist_shuffle_tracks", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("playlist_hide_track_numbers", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("readiness_status", sa.String(length=80), nullable=False, server_default="needs_review"),
        sa.Column("readiness_detail", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_library_items_content_type", "library_items", ["content_type"])
    op.create_index("ix_library_items_readiness_status", "library_items", ["readiness_status"])
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
        sa.Column("related_card_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_pending_delete", "jobs", ["pending_delete"])
    op.create_index("ix_jobs_type", "jobs", ["type"])
    op.create_index("ix_jobs_related_card_id", "jobs", ["related_card_id"])

    op.create_table(
        "physical_cards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("card_code", sa.String(length=80), nullable=False),
        sa.Column("programmable_id", sa.String(length=160), nullable=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("card_kind", sa.String(length=80), nullable=False),
        sa.Column("nfc_technology", sa.String(length=120), nullable=True),
        sa.Column("chip_type", sa.String(length=120), nullable=True),
        sa.Column("memory_size_bytes", sa.Integer(), nullable=True),
        sa.Column("ndef_prepared", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ndef_format_command", sa.String(length=500), nullable=True),
        sa.Column("programming_app", sa.String(length=120), nullable=True),
        sa.Column("source_card_code", sa.String(length=80), nullable=True),
        sa.Column("is_reusable_transfer_card", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ready_to_link_in_app", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("linked_manually", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("overwrite_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("downloaded_to_player_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("needs_player_download", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("current_library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=True),
        sa.Column("pending_job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("yoto_playlist_uri", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("label_color", sa.String(length=80), nullable=True),
        sa.Column("tested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_programmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("card_code", name="uq_physical_cards_card_code"),
    )
    op.create_index("ix_physical_cards_card_code", "physical_cards", ["card_code"])
    op.create_index("ix_physical_cards_programmable_id", "physical_cards", ["programmable_id"])
    op.create_index("ix_physical_cards_status", "physical_cards", ["status"])

    op.create_table(
        "playlist_tracks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("track_number", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("icon_path", sa.Text(), nullable=True),
        sa.Column("track_behavior", sa.String(length=80), nullable=False),
        sa.Column("is_stream", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("stream_url", sa.Text(), nullable=True),
        sa.Column("podcast_episode_guid", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_playlist_tracks_library_item_id", "playlist_tracks", ["library_item_id"])
    op.create_index("ix_playlist_tracks_track_number", "playlist_tracks", ["track_number"])

    op.create_table(
        "podcast_feeds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("rss_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("artwork_url", sa.Text(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_podcast_feeds_library_item_id", "podcast_feeds", ["library_item_id"])

    op.create_table(
        "podcast_episodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feed_id", sa.Integer(), sa.ForeignKey("podcast_feeds.id"), nullable=False),
        sa.Column("guid", sa.String(length=500), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("episode_url", sa.Text(), nullable=True),
        sa.Column("published_at", sa.String(length=120), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("selected_for_playlist", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_podcast_episodes_feed_id", "podcast_episodes", ["feed_id"])

    op.create_table(
        "split_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=False),
        sa.Column("timestamp_seconds", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_split_points_library_item_id", "split_points", ["library_item_id"])

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
            {
                "key": "yoto_api_enabled",
                "value": "false",
                "description": "Whether Yoto API integration is enabled.",
            },
            {
                "key": "yoto_api_base_url",
                "value": "https://api.yotoplay.com",
                "description": "Base URL for Yoto API requests.",
            },
            {
                "key": "yoto_auth_base_url",
                "value": "https://login.yotoplay.com",
                "description": "Base URL for Yoto authentication requests.",
            },
            {
                "key": "yoto_client_id",
                "value": "dNHlYDxvjov4zHB3pm27FvdbtcljK5VL",
                "description": "Non-secret Yoto OAuth client identifier, if required.",
            },
            {
                "key": "yoto_redirect_uri",
                "value": "http://ziggi-pc.tailaf3d4b.ts.net:5175/settings/yoto/callback",
                "description": "Yoto OAuth redirect URI, if required.",
            },
            {
                "key": "yoto_oauth_scope",
                "value": (
                    "openid offline_access "
                    "family:library:view family:library:manage "
                    "user:content:view user:content:manage "
                    "family:devices:view family:devices:manage family:devices:control"
                ),
                "description": "Requested Yoto OAuth scopes.",
            },
            {
                "key": "yoto_upload_timeout_seconds",
                "value": "900",
                "description": "Timeout for Yoto asset upload jobs.",
            },
            {
                "key": "yoto_transcode_poll_seconds",
                "value": "10",
                "description": "Polling interval for Yoto transcode status.",
            },
            {
                "key": "yoto_transcode_timeout_minutes",
                "value": "30",
                "description": "Timeout for waiting on Yoto transcode status.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_split_points_library_item_id", table_name="split_points")
    op.drop_table("split_points")
    op.drop_index("ix_podcast_episodes_feed_id", table_name="podcast_episodes")
    op.drop_table("podcast_episodes")
    op.drop_index("ix_podcast_feeds_library_item_id", table_name="podcast_feeds")
    op.drop_table("podcast_feeds")
    op.drop_index("ix_playlist_tracks_track_number", table_name="playlist_tracks")
    op.drop_index("ix_playlist_tracks_library_item_id", table_name="playlist_tracks")
    op.drop_table("playlist_tracks")
    op.drop_index("ix_physical_cards_status", table_name="physical_cards")
    op.drop_index("ix_physical_cards_programmable_id", table_name="physical_cards")
    op.drop_index("ix_physical_cards_card_code", table_name="physical_cards")
    op.drop_table("physical_cards")
    op.drop_index("ix_jobs_related_card_id", table_name="jobs")
    op.drop_index("ix_jobs_type", table_name="jobs")
    op.drop_index("ix_jobs_pending_delete", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_library_items_title", table_name="library_items")
    op.drop_index("ix_library_items_status", table_name="library_items")
    op.drop_index("ix_library_items_readiness_status", table_name="library_items")
    op.drop_index("ix_library_items_content_type", table_name="library_items")
    op.drop_table("library_items")
    op.drop_index("ix_import_requests_status", table_name="import_requests")
    op.drop_index("ix_import_requests_source_type", table_name="import_requests")
    op.drop_index("ix_import_requests_pending_delete", table_name="import_requests")
    op.drop_index("ix_import_requests_content_type", table_name="import_requests")
    op.drop_table("import_requests")
    op.drop_index("ix_settings_key", table_name="settings")
    op.drop_table("settings")
