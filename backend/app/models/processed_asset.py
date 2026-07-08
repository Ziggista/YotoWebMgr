from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedAsset(Base):
    __tablename__ = "processed_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    playlist_track_id: Mapped[int | None] = mapped_column(ForeignKey("playlist_tracks.id"), nullable=True, index=True)
    source_path: Mapped[str] = mapped_column(Text)
    output_path: Mapped[str] = mapped_column(Text)
    codec: Mapped[str] = mapped_column(String(80), default="mp3")
    bitrate_kbps: Mapped[int] = mapped_column(Integer)
    channels: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    profile: Mapped[str] = mapped_column(String(80))
    settings_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
