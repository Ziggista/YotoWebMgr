from datetime import UTC, datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import CardAssignmentEvent, CardScanDump, PhysicalCard
from app.schemas.foundation import (
    CardAssignmentEventResponse,
    CardCreate,
    CardResponse,
    CardScanDumpEntry,
    CardScanDumpRequest,
    CardScanDumpResponse,
    CardUpdate,
)


router = APIRouter()
logger = logging.getLogger("app.cards")


def _build_card_response(card: PhysicalCard) -> CardResponse:
    return CardResponse(
        id=card.id,
        card_code=card.card_code,
        programmable_id=card.programmable_id,
        nfc_serial_number=card.nfc_serial_number,
        ndef_payload_text=card.ndef_payload_text,
        ndef_payload_hex=card.ndef_payload_hex,
        scan_source=card.scan_source,
        display_name=card.display_name,
        card_kind=card.card_kind,
        nfc_technology=card.nfc_technology,
        chip_type=card.chip_type,
        memory_size_bytes=card.memory_size_bytes,
        ndef_prepared=card.ndef_prepared,
        ndef_format_command=card.ndef_format_command,
        programming_app=card.programming_app,
        source_card_code=card.source_card_code,
        is_reusable_transfer_card=card.is_reusable_transfer_card,
        ready_to_link_in_app=card.ready_to_link_in_app,
        linked_manually=card.linked_manually,
        overwrite_ok=card.overwrite_ok,
        downloaded_to_player_confirmed=card.downloaded_to_player_confirmed,
        needs_player_download=card.needs_player_download,
        current_library_item_id=card.current_library_item_id,
        pending_job_id=card.pending_job_id,
        yoto_playlist_uri=card.yoto_playlist_uri,
        status=card.status,
        label_color=card.label_color,
        tested=card.tested,
        last_scanned_at=card.last_scanned_at,
        last_linked_at=card.last_linked_at,
        last_programmed_at=card.last_programmed_at,
        last_tested_at=card.last_tested_at,
        notes=card.notes,
        created_at=card.created_at,
    )


def _build_card_assignment_event_response(event: CardAssignmentEvent) -> CardAssignmentEventResponse:
    return CardAssignmentEventResponse.model_validate(event, from_attributes=True)


def _build_card_scan_dump_response(entry: CardScanDump) -> CardScanDumpEntry:
    return CardScanDumpEntry(
        id=entry.id,
        scan_source=entry.scan_source,
        runtime=entry.runtime,
        programmable_id=entry.programmable_id,
        nfc_serial_number=entry.nfc_serial_number,
        ndef_payload_text=entry.ndef_payload_text,
        ndef_payload_hex=entry.ndef_payload_hex,
        tag_info=entry.tag_info,
        records=entry.records or [],
        created_at=entry.created_at,
    )


@router.get("", response_model=list[CardResponse])
async def list_cards(db: Annotated[Session, Depends(get_db_session)]) -> list[CardResponse]:
    query = select(PhysicalCard).order_by(PhysicalCard.card_code.asc(), PhysicalCard.id.asc())
    return [_build_card_response(card) for card in db.scalars(query)]


@router.get("/scan-dumps", response_model=list[CardScanDumpEntry])
async def list_card_scan_dumps(
    db: Annotated[Session, Depends(get_db_session)],
) -> list[CardScanDumpEntry]:
    dumps = db.scalars(
        select(CardScanDump).order_by(CardScanDump.created_at.desc(), CardScanDump.id.desc()).limit(20)
    )
    return [_build_card_scan_dump_response(entry) for entry in dumps]


@router.post("/scan-dumps", response_model=CardScanDumpResponse, status_code=202)
async def create_card_scan_dump(
    payload: CardScanDumpRequest,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardScanDumpResponse:
    dumped_at = datetime.now(UTC)
    entry = CardScanDump(
        scan_source=payload.scan_source,
        runtime=payload.runtime,
        programmable_id=payload.programmable_id,
        nfc_serial_number=payload.nfc_serial_number,
        ndef_payload_text=payload.ndef_payload_text,
        ndef_payload_hex=payload.ndef_payload_hex,
        tag_info=payload.tag_info,
        records=payload.records,
    )
    db.add(entry)
    db.commit()
    logger.info(
        "CARD_SCAN_DUMP %s",
        payload.model_dump_json(),
    )
    return CardScanDumpResponse(
        status="accepted",
        detail="Captured card scan dump in backend logs.",
        dumped_at=dumped_at,
    )


@router.get("/{card_id}", response_model=CardResponse)
async def get_card(
    card_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardResponse:
    card = db.get(PhysicalCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return _build_card_response(card)


@router.get("/{card_id}/history", response_model=list[CardAssignmentEventResponse])
async def list_card_assignment_history(
    card_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[CardAssignmentEventResponse]:
    card = db.get(PhysicalCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    events = db.scalars(
        select(CardAssignmentEvent)
        .where(CardAssignmentEvent.card_id == card.id)
        .order_by(CardAssignmentEvent.created_at.desc(), CardAssignmentEvent.id.desc())
    )
    return [_build_card_assignment_event_response(event) for event in events]


@router.post("", response_model=CardResponse, status_code=201)
async def create_card(
    payload: CardCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardResponse:
    card_payload = payload.model_dump()
    if not card_payload.get("programmable_id") and card_payload.get("nfc_serial_number"):
        card_payload["programmable_id"] = card_payload["nfc_serial_number"]
    card = PhysicalCard(**card_payload)
    db.add(card)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Card ID already exists.",
        ) from error
    db.refresh(card)
    return _build_card_response(card)


@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: int,
    payload: CardUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardResponse:
    card = db.get(PhysicalCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    previous_status = card.status
    previous_playlist_uri = card.yoto_playlist_uri
    previous_library_item_id = card.current_library_item_id
    updates = payload.model_dump(exclude_unset=True)
    now = datetime.now(UTC)
    scan_fields = {"programmable_id", "nfc_serial_number", "ndef_payload_text", "ndef_payload_hex", "scan_source"}

    if updates.get("ndef_prepared") is True and not card.ndef_prepared:
        updates.setdefault("last_programmed_at", now)
    if updates.get("linked_manually") is True and not card.linked_manually:
        updates.setdefault("last_linked_at", now)
    if updates.get("downloaded_to_player_confirmed") is True:
        updates["needs_player_download"] = False
    if updates.get("tested") is True and not card.tested:
        updates.setdefault("last_tested_at", now)
    if any(field in updates for field in scan_fields):
        updates.setdefault("last_scanned_at", now)
    if (
        not updates.get("programmable_id")
        and "nfc_serial_number" in updates
        and updates.get("nfc_serial_number")
        and not card.programmable_id
    ):
        updates["programmable_id"] = updates["nfc_serial_number"]

    for field, value in updates.items():
        setattr(card, field, value)

    if updates:
        changed_fields = ", ".join(sorted(updates.keys()))
        db.add(
            CardAssignmentEvent(
                card_id=card.id,
                event_type="card_workflow_updated",
                previous_library_item_id=previous_library_item_id,
                library_item_id=card.current_library_item_id,
                previous_status=previous_status,
                new_status=card.status,
                previous_yoto_playlist_uri=previous_playlist_uri,
                yoto_playlist_uri=card.yoto_playlist_uri,
                summary=f"Updated card workflow fields: {changed_fields}",
            )
        )

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Card ID already exists.",
        ) from error
    db.refresh(card)
    return _build_card_response(card)

