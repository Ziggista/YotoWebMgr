from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_start_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_end_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    track_number: Mapped[int] = mapped_column(Integer, default=1, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    icon_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    track_behavior: Mapped[str] = mapped_column(String(80), default="continue")
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False)
    stream_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    podcast_episode_guid: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PodcastFeed(Base):
    __tablename__ = "podcast_feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    rss_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(240), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    artwork_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class PodcastEpisode(Base):
    __tablename__ = "podcast_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    feed_id: Mapped[int] = mapped_column(ForeignKey("podcast_feeds.id"), index=True)
    guid: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    episode_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_for_playlist: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class SplitPoint(Base):
    __tablename__ = "split_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    timestamp_seconds: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    part_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class CardPlanPart(Base):
    __tablename__ = "card_plan_parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    part_number: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(240))
    estimated_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    estimated_size_mb: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class CardPlanTrackAssignment(Base):
    __tablename__ = "card_plan_track_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_plan_part_id: Mapped[int] = mapped_column(ForeignKey("card_plan_parts.id"), index=True)
    playlist_track_id: Mapped[int] = mapped_column(ForeignKey("playlist_tracks.id"), index=True)
    track_order: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class YotoPlaylistDraft(Base):
    __tablename__ = "yoto_playlist_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    related_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(80), default="draft", index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    remote_playlist_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    remote_playlist_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
