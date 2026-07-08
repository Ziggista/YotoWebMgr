from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArtworkAsset(Base):
    __tablename__ = "artwork_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_item_id: Mapped[int] = mapped_column(ForeignKey("library_items.id"), index=True)
    source_artwork_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(80), default="available", index=True)
    source_path: Mapped[str] = mapped_column(Text)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    palette: Mapped[str | None] = mapped_column(String(80), nullable=True)
    settings_json: Mapped[str] = mapped_column(Text, default="{}")
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
