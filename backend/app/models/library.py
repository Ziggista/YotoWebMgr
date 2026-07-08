from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LibraryItem(Base):
    __tablename__ = "library_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(240), index=True)
    content_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(64), default="draft", index=True)
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_import_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_requests.id"),
        nullable=True,
    )
    cover_art_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    playlist_always_play_from_start: Mapped[bool] = mapped_column(Boolean, default=False)
    playlist_shuffle_tracks: Mapped[bool] = mapped_column(Boolean, default=False)
    playlist_hide_track_numbers: Mapped[bool] = mapped_column(Boolean, default=False)
    readiness_status: Mapped[str] = mapped_column(String(80), default="needs_review", index=True)
    readiness_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
