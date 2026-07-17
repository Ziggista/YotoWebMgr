from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PhysicalCard(Base):
    __tablename__ = "physical_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    programmable_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    nfc_serial_number: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    ndef_payload_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ndef_payload_hex: Mapped[str | None] = mapped_column(Text, nullable=True)
    scan_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    display_name: Mapped[str] = mapped_column(String(160))
    card_kind: Mapped[str] = mapped_column(String(80), default="official_myo")
    nfc_technology: Mapped[str | None] = mapped_column(String(120), nullable=True)
    chip_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    memory_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ndef_prepared: Mapped[bool] = mapped_column(Boolean, default=False)
    ndef_format_command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    programming_app: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_card_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    is_reusable_transfer_card: Mapped[bool] = mapped_column(Boolean, default=False)
    ready_to_link_in_app: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_manually: Mapped[bool] = mapped_column(Boolean, default=False)
    overwrite_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    downloaded_to_player_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    needs_player_download: Mapped[bool] = mapped_column(Boolean, default=False)
    current_library_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("library_items.id"),
        nullable=True,
    )
    pending_job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    yoto_playlist_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(80), default="available", index=True)
    label_color: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tested: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_linked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_programmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class CardAssignmentEvent(Base):
    __tablename__ = "card_assignment_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("physical_cards.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    previous_library_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    library_item_id: Mapped[int | None] = mapped_column(ForeignKey("library_items.id"), nullable=True, index=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    previous_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(80), nullable=True)
    previous_yoto_playlist_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    yoto_playlist_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary: Mapped[str] = mapped_column(String(240))
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CardScanDump(Base):
    __tablename__ = "card_scan_dumps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_source: Mapped[str] = mapped_column(String(80), index=True)
    runtime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    programmable_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    nfc_serial_number: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    ndef_payload_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ndef_payload_hex: Mapped[str | None] = mapped_column(Text, nullable=True)
    tag_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    records: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
