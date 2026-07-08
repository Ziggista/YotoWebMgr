from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ContentType = Literal[
    "Audiobook",
    "Music Album",
    "Story Collection",
    "Podcast",
    "Radio Play",
    "Sleep Sounds",
    "Custom Playlist",
    "Other Audio",
]
ImportSourceType = Literal["browser_upload", "filesystem", "plex"]
JobStatus = Literal["queued", "running", "waiting", "succeeded", "failed", "cancelled", "retrying"]
TrackBehavior = Literal["continue", "pause_for_button", "repeat_track"]


class AppSettings(BaseModel):
    target_duration_hours: float
    target_size_mb: int
    normalise_loudness_default: bool
    audiobook_bitrate_kbps: int
    music_bitrate_kbps: int
    yoto_api_enabled: bool
    yoto_api_base_url: str
    yoto_auth_base_url: str
    yoto_client_id: str
    yoto_redirect_uri: str
    yoto_oauth_scope: str
    yoto_upload_timeout_seconds: int
    yoto_transcode_poll_seconds: int
    yoto_transcode_timeout_minutes: int


class SettingsUpdate(BaseModel):
    target_duration_hours: float | None = Field(default=None, gt=0)
    target_size_mb: int | None = Field(default=None, gt=0)
    normalise_loudness_default: bool | None = None
    audiobook_bitrate_kbps: int | None = Field(default=None, gt=0)
    music_bitrate_kbps: int | None = Field(default=None, gt=0)
    yoto_api_enabled: bool | None = None
    yoto_api_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    yoto_auth_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    yoto_client_id: str | None = Field(default=None, max_length=500)
    yoto_redirect_uri: str | None = Field(default=None, max_length=500)
    yoto_oauth_scope: str | None = Field(default=None, max_length=500)
    yoto_upload_timeout_seconds: int | None = Field(default=None, gt=0)
    yoto_transcode_poll_seconds: int | None = Field(default=None, gt=0)
    yoto_transcode_timeout_minutes: int | None = Field(default=None, gt=0)


class LibraryItemResponse(BaseModel):
    id: int
    title: str
    content_type: str
    status: str
    cover_art_path: str | None = None
    playlist_always_play_from_start: bool = False
    playlist_shuffle_tracks: bool = False
    playlist_hide_track_numbers: bool = False
    readiness_status: str = "needs_review"
    readiness_detail: str | None = None
    notes: str | None
    created_at: datetime
    media_url: str | None = None
    stream_url: str | None = None


class LibraryItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content_type: ContentType
    cover_art_path: str | None = Field(default=None, max_length=2000)
    playlist_always_play_from_start: bool = False
    playlist_shuffle_tracks: bool = False
    playlist_hide_track_numbers: bool = False
    notes: str | None = Field(default=None, max_length=2000)
    owner_user_slug: str | None = Field(default=None, min_length=1)


class LibraryItemSettingsUpdate(BaseModel):
    cover_art_path: str | None = Field(default=None, max_length=2000)
    playlist_always_play_from_start: bool | None = None
    playlist_shuffle_tracks: bool | None = None
    playlist_hide_track_numbers: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PlaylistTrackCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    source_path: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    source_start_seconds: int | None = Field(default=None, ge=0)
    source_end_seconds: int | None = Field(default=None, ge=0)
    track_number: int = Field(default=1, gt=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    icon_path: str | None = Field(default=None, max_length=2000)
    track_behavior: TrackBehavior = "continue"
    is_stream: bool = False
    stream_url: str | None = Field(default=None, max_length=2000)
    podcast_episode_guid: str | None = Field(default=None, max_length=500)


class PlaylistTrackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    source_url: str | None = Field(default=None, max_length=2000)
    source_start_seconds: int | None = Field(default=None, ge=0)
    source_end_seconds: int | None = Field(default=None, ge=0)
    track_number: int | None = Field(default=None, gt=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    icon_path: str | None = Field(default=None, max_length=2000)
    track_behavior: TrackBehavior | None = None
    stream_url: str | None = Field(default=None, max_length=2000)


class PlaylistTrackResponse(BaseModel):
    id: int
    library_item_id: int
    title: str
    source_path: str | None
    source_url: str | None
    source_start_seconds: int | None
    source_end_seconds: int | None
    track_number: int
    duration_seconds: int | None
    icon_path: str | None
    track_behavior: str
    is_stream: bool
    stream_url: str | None
    podcast_episode_guid: str | None
    created_at: datetime


class TrackIconApplyRequest(BaseModel):
    icon_path: str = Field(min_length=1, max_length=2000)


class RadioStreamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    stream_url: str = Field(min_length=1, max_length=2000)
    icon_path: str | None = Field(default=None, max_length=2000)
    track_number: int | None = Field(default=None, gt=0)


class PodcastFeedCreate(BaseModel):
    rss_url: str = Field(min_length=1, max_length=2000)
    title: str | None = Field(default=None, max_length=240)
    rss_xml: str | None = Field(default=None, max_length=500000)


class PodcastEpisodeResponse(BaseModel):
    id: int
    feed_id: int
    guid: str | None
    title: str
    description: str | None
    episode_url: str | None
    published_at: str | None
    duration_seconds: int | None
    selected_for_playlist: bool
    created_at: datetime


class PodcastFeedResponse(BaseModel):
    id: int
    library_item_id: int
    rss_url: str
    title: str | None
    description: str | None
    artwork_url: str | None
    last_fetched_at: datetime | None
    created_at: datetime
    episodes: list[PodcastEpisodeResponse] = []


class SplitPointCreate(BaseModel):
    timestamp_seconds: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=240)
    part_number: int | None = Field(default=None, gt=0)


class SplitPointResponse(BaseModel):
    id: int
    library_item_id: int
    timestamp_seconds: int
    title: str
    part_number: int | None
    created_at: datetime


class LibraryItemDetailResponse(BaseModel):
    item: LibraryItemResponse
    tracks: list[PlaylistTrackResponse]
    podcast_feeds: list[PodcastFeedResponse]
    split_points: list[SplitPointResponse]
    processed_assets: list["ProcessedAssetResponse"] = []


class ProcessedAssetResponse(BaseModel):
    id: int
    library_item_id: int
    playlist_track_id: int | None
    source_path: str
    output_path: str
    codec: str
    bitrate_kbps: int
    channels: int
    duration_seconds: int | None
    size_bytes: int
    checksum_sha256: str
    profile: str
    settings_json: str
    created_at: datetime


class VersionEventResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    version_number: int
    event_type: str
    summary: str
    snapshot_json: str
    created_by_user_id: int | None
    created_at: datetime


class VersionRestoreResponse(BaseModel):
    restored_from_version_id: int
    restored_version_number: int
    library_item: LibraryItemDetailResponse
    version_event: VersionEventResponse


class ReadinessCheck(BaseModel):
    key: str
    label: str
    ok: bool
    detail: str


class ReadinessResponse(BaseModel):
    library_item_id: int
    status: str
    checks: list[ReadinessCheck]


class CardPlanTrackResponse(BaseModel):
    track_id: int
    title: str
    track_number: int
    duration_seconds: int | None
    estimated_size_mb: float | None


class CardPlanPartResponse(BaseModel):
    part_number: int
    title: str
    duration_seconds: int
    estimated_size_mb: float
    track_count: int
    tracks: list[CardPlanTrackResponse]
    warnings: list[str] = []


class CardPlanResponse(BaseModel):
    library_item_id: int
    target_duration_seconds: int
    target_size_mb: int
    total_duration_seconds: int
    estimated_total_size_mb: float
    parts: list[CardPlanPartResponse]
    warnings: list[str] = []


class CardPlanTrackAssignmentSave(BaseModel):
    track_id: int = Field(gt=0)
    track_order: int = Field(default=1, gt=0)


class CardPlanPartSave(BaseModel):
    part_number: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=240)
    track_ids: list[int] | None = None
    tracks: list[CardPlanTrackAssignmentSave] | None = None


class CardPlanSaveRequest(BaseModel):
    parts: list[CardPlanPartSave] = Field(min_length=1)


class ImportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    source_type: ImportSourceType
    source_path: str | None = Field(default=None, max_length=2000)
    content_type: ContentType
    requested_by_user_slug: str | None = Field(default=None, min_length=1)


class ImportSourceInfo(BaseModel):
    filesystem_drop_path: str
    browser_upload_path: str
    allowed_extensions: list[str]


class ImportResponse(BaseModel):
    id: int
    title: str
    source_type: str
    source_path: str | None
    content_type: str
    status: str
    pending_delete: bool = False
    created_at: datetime
    related_library_item_id: int | None = None
    related_job_id: int | None = None


class JobResponse(BaseModel):
    id: int
    type: str
    status: str
    pending_delete: bool
    retry_count: int
    max_retries: int
    progress_percent: int
    progress_message: str
    error_summary: str | None
    related_library_item_id: int | None
    related_import_id: int | None
    related_card_id: int | None = None
    created_at: datetime


class CardCreate(BaseModel):
    card_code: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9]+$")
    programmable_id: str | None = Field(default=None, max_length=160)
    display_name: str = Field(min_length=1, max_length=160)
    card_kind: str = Field(default="official_myo", max_length=80)
    nfc_technology: str | None = Field(default=None, max_length=120)
    chip_type: str | None = Field(default=None, max_length=120)
    memory_size_bytes: int | None = Field(default=None, gt=0)
    ndef_prepared: bool = False
    ndef_format_command: str | None = Field(default=None, max_length=500)
    programming_app: str | None = Field(default=None, max_length=120)
    source_card_code: str | None = Field(default=None, max_length=80)
    is_reusable_transfer_card: bool = False
    ready_to_link_in_app: bool = False
    linked_manually: bool = False
    overwrite_ok: bool = False
    downloaded_to_player_confirmed: bool = False
    needs_player_download: bool = False
    yoto_playlist_uri: str | None = Field(default=None, max_length=500)
    status: str = Field(default="available", max_length=80)
    label_color: str | None = Field(default=None, max_length=80)
    tested: bool = False
    last_linked_at: datetime | None = None
    last_programmed_at: datetime | None = None
    last_tested_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class CardResponse(BaseModel):
    id: int
    card_code: str
    programmable_id: str | None
    display_name: str
    card_kind: str
    nfc_technology: str | None
    chip_type: str | None
    memory_size_bytes: int | None
    ndef_prepared: bool
    ndef_format_command: str | None
    programming_app: str | None
    source_card_code: str | None
    is_reusable_transfer_card: bool
    ready_to_link_in_app: bool
    linked_manually: bool
    overwrite_ok: bool
    downloaded_to_player_confirmed: bool
    needs_player_download: bool
    current_library_item_id: int | None
    pending_job_id: int | None
    yoto_playlist_uri: str | None
    status: str
    label_color: str | None
    tested: bool
    last_linked_at: datetime | None
    last_programmed_at: datetime | None
    last_tested_at: datetime | None
    notes: str | None
    created_at: datetime


class LinkCardRequest(BaseModel):
    card_id: int = Field(gt=0)


class LinkCardResponse(BaseModel):
    library_item: LibraryItemResponse
    card: CardResponse
    job: JobResponse
    requires_split_plan: bool
    estimated_source_size_mb: float | None


class YotoConfigResponse(BaseModel):
    enabled: bool
    api_base_url: str
    auth_base_url: str
    client_id_configured: bool
    redirect_uri_configured: bool
    oauth_scope: str


class YotoPlaylistPreviewResponse(BaseModel):
    library_item_id: int
    payload: dict[str, object]
    live_api_call: bool = False


class YotoPlaylistDraftResponse(BaseModel):
    id: int
    library_item_id: int
    related_job_id: int | None
    title: str
    status: str
    payload: dict[str, object]
    remote_playlist_id: str | None
    remote_playlist_uri: str | None
    last_error: str | None
    created_at: datetime


class QueueYotoPlaylistResponse(BaseModel):
    playlist: YotoPlaylistDraftResponse
    job: JobResponse
    live_api_call: bool = False
