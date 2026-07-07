from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import Setting
from app.schemas.foundation import AppSettings, SettingsUpdate


router = APIRouter()

SETTING_DEFAULTS = {
    "target_duration_hours": "4.9",
    "target_size_mb": "480",
    "normalise_loudness_default": "true",
    "audiobook_bitrate_kbps": "96",
    "music_bitrate_kbps": "128",
}


def _coerce_settings(records: dict[str, str]) -> AppSettings:
    values = SETTING_DEFAULTS | records
    return AppSettings(
        target_duration_hours=float(values["target_duration_hours"]),
        target_size_mb=int(values["target_size_mb"]),
        normalise_loudness_default=values["normalise_loudness_default"].lower() == "true",
        audiobook_bitrate_kbps=int(values["audiobook_bitrate_kbps"]),
        music_bitrate_kbps=int(values["music_bitrate_kbps"]),
    )


@router.get("", response_model=AppSettings)
async def get_settings(db: Annotated[Session, Depends(get_db_session)]) -> AppSettings:
    records = {record.key: record.value for record in db.scalars(select(Setting))}
    return _coerce_settings(records)


@router.put("", response_model=AppSettings)
async def update_settings(
    payload: SettingsUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> AppSettings:
    updates = payload.model_dump(exclude_none=True)
    for key, value in updates.items():
        stored_value = "true" if value is True else "false" if value is False else str(value)
        setting = db.scalar(select(Setting).where(Setting.key == key))
        if setting is None:
            setting = Setting(key=key, value=stored_value)
        else:
            setting.value = stored_value
        db.add(setting)
    db.commit()

    records = {record.key: record.value for record in db.scalars(select(Setting))}
    return _coerce_settings(records)
