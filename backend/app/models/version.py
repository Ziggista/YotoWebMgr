from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class VersionEvent(Base):
    __tablename__ = "version_events"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "version_number", name="uq_version_events_entity_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    summary: Mapped[str] = mapped_column(String(240))
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
