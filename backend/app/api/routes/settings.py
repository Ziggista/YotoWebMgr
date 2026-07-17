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
    "yoto_api_enabled": "false",
    "yoto_api_base_url": "https://api.yotoplay.com",
    "yoto_auth_base_url": "https://login.yotoplay.com",
    "yoto_client_id": "dNHlYDxvjov4zHB3pm27FvdbtcljK5VL",
    "yoto_redirect_uri": "http://ziggi-pc.tailaf3d4b.ts.net:5175/settings/yoto/callback",
    "yoto_oauth_scope": (
        "openid offline_access "
        "family:library:view family:library:manage "
        "user:content:view user:content:manage "
        "family:devices:view family:devices:manage family:devices:control"
    ),
    "yoto_upload_timeout_seconds": "900",
    "yoto_transcode_poll_seconds": "10",
    "yoto_transcode_timeout_minutes": "30",
}


def _coerce_settings(records: dict[str, str]) -> AppSettings:
    values = SETTING_DEFAULTS | records
    return AppSettings(
        target_duration_hours=float(values["target_duration_hours"]),
        target_size_mb=int(values["target_size_mb"]),
        normalise_loudness_default=values["normalise_loudness_default"].lower() == "true",
        audiobook_bitrate_kbps=int(values["audiobook_bitrate_kbps"]),
        music_bitrate_kbps=int(values["music_bitrate_kbps"]),
        yoto_api_enabled=values["yoto_api_enabled"].lower() == "true",
        yoto_api_base_url=values["yoto_api_base_url"],
        yoto_auth_base_url=values["yoto_auth_base_url"],
        yoto_client_id=values["yoto_client_id"],
        yoto_redirect_uri=values["yoto_redirect_uri"],
        yoto_oauth_scope=values["yoto_oauth_scope"],
        yoto_upload_timeout_seconds=int(values["yoto_upload_timeout_seconds"]),
        yoto_transcode_poll_seconds=int(values["yoto_transcode_poll_seconds"]),
        yoto_transcode_timeout_minutes=int(values["yoto_transcode_timeout_minutes"]),
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
