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


class AppSettings(BaseModel):
    target_duration_hours: float
    target_size_mb: int
    normalise_loudness_default: bool
    audiobook_bitrate_kbps: int
    music_bitrate_kbps: int


class SettingsUpdate(BaseModel):
    target_duration_hours: float | None = Field(default=None, gt=0)
    target_size_mb: int | None = Field(default=None, gt=0)
    normalise_loudness_default: bool | None = None
    audiobook_bitrate_kbps: int | None = Field(default=None, gt=0)
    music_bitrate_kbps: int | None = Field(default=None, gt=0)


class LibraryItemResponse(BaseModel):
    id: int
    title: str
    content_type: str
    status: str
    notes: str | None
    created_at: datetime
    media_url: str | None = None


class LibraryItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    content_type: ContentType
    notes: str | None = Field(default=None, max_length=2000)
    owner_user_slug: str | None = Field(default=None, min_length=1)


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
    created_at: datetime
