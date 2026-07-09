from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class YotoCredentialState(Base):
    __tablename__ = "yoto_credential_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_label: Mapped[str] = mapped_column(String(120), default="Household Yoto")
    status: Mapped[str] = mapped_column(String(80), default="not_connected", index=True)
    token_storage_ref: Mapped[str | None] = mapped_column(String(240), nullable=True)
    masked_account_id: Mapped[str | None] = mapped_column(String(240), nullable=True)
    masked_email: Mapped[str | None] = mapped_column(String(240), nullable=True)
    scopes: Mapped[str] = mapped_column(Text, default="")
    authorization_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_state: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
