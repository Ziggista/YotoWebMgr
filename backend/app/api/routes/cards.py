from datetime import UTC, datetime
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import (
    CardAssignmentEvent,
    CardProgrammingEvent,
    CardProgrammingSession,
    CardScanDump,
    PhysicalCard,
)
from app.schemas.foundation import (
    CardAssignmentEventResponse,
    CardCreate,
    CardProgrammingEventCreate,
    CardProgrammingEventResponse,
    CardProgrammingSessionResponse,
    CardProgrammingSessionUpdate,
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


def _build_card_programming_event_response(event: CardProgrammingEvent) -> CardProgrammingEventResponse:
    return CardProgrammingEventResponse(
        id=event.id,
        card_id=event.card_id,
        card_code=event.card_code,
        event_type=event.event_type,
        runtime=event.runtime,
        source=event.source,
        target_label=event.target_label,
        detail=event.detail,
        compared_field=event.compared_field,
        matched=event.matched,
        playlist_uri=event.playlist_uri,
        programmable_id=event.programmable_id,
        nfc_serial_number=event.nfc_serial_number,
        ndef_payload_text=event.ndef_payload_text,
        ndef_payload_hex=event.ndef_payload_hex,
        observed_programmable_id=event.observed_programmable_id,
        observed_nfc_serial_number=event.observed_nfc_serial_number,
        observed_ndef_payload_text=event.observed_ndef_payload_text,
        observed_ndef_payload_hex=event.observed_ndef_payload_hex,
        extra_json=event.extra_json,
        created_at=event.created_at,
    )


def _build_card_programming_session_response(session: CardProgrammingSession) -> CardProgrammingSessionResponse:
    return CardProgrammingSessionResponse(
        id=session.id,
        session_key=session.session_key,
        active_card_id=session.active_card_id,
        source=session.source,
        target_label=session.target_label,
        detail=session.detail,
        library_item_id=session.library_item_id,
        playlist_draft_id=session.playlist_draft_id,
        playlist_uri=session.playlist_uri,
        programmable_id=session.programmable_id,
        ndef_payload_text=session.ndef_payload_text,
        ndef_payload_hex=session.ndef_payload_hex,
        source_scan_dump_id=session.source_scan_dump_id,
        verification_armed=session.verification_armed,
        last_verification_event_id=session.last_verification_event_id,
        extra_json=session.extra_json,
        created_at=session.created_at,
        updated_at=session.updated_at,
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


@router.get("/programming-events", response_model=list[CardProgrammingEventResponse])
async def list_card_programming_events(
    db: Annotated[Session, Depends(get_db_session)],
) -> list[CardProgrammingEventResponse]:
    events = db.scalars(
        select(CardProgrammingEvent)
        .order_by(CardProgrammingEvent.created_at.desc(), CardProgrammingEvent.id.desc())
        .limit(50)
    )
    return [_build_card_programming_event_response(event) for event in events]


@router.get("/programming-session", response_model=CardProgrammingSessionResponse)
async def get_card_programming_session(
    session_key: str = "default",
    db: Annotated[Session, Depends(get_db_session)] = None,
) -> CardProgrammingSessionResponse:
    session = db.scalar(select(CardProgrammingSession).where(CardProgrammingSession.session_key == session_key))
    if session is None:
        session = CardProgrammingSession(session_key=session_key)
        db.add(session)
        db.commit()
        db.refresh(session)
    return _build_card_programming_session_response(session)


@router.put("/programming-session", response_model=CardProgrammingSessionResponse)
async def update_card_programming_session(
    payload: CardProgrammingSessionUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardProgrammingSessionResponse:
    session = db.scalar(
        select(CardProgrammingSession).where(CardProgrammingSession.session_key == payload.session_key)
    )
    if session is None:
        session = CardProgrammingSession(session_key=payload.session_key)
        db.add(session)
        db.flush()

    if payload.clear:
        session.active_card_id = None
        session.source = None
        session.target_label = None
        session.detail = None
        session.library_item_id = None
        session.playlist_draft_id = None
        session.playlist_uri = None
        session.programmable_id = None
        session.ndef_payload_text = None
        session.ndef_payload_hex = None
        session.source_scan_dump_id = None
        session.verification_armed = False
        session.last_verification_event_id = None
        session.extra_json = None
    else:
        if payload.active_card_id is not None:
            if db.get(PhysicalCard, payload.active_card_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
            session.active_card_id = payload.active_card_id
        if payload.source is not None:
            session.source = payload.source
        if payload.target_label is not None:
            session.target_label = payload.target_label
        if payload.detail is not None:
            session.detail = payload.detail
        if payload.library_item_id is not None:
            session.library_item_id = payload.library_item_id
        if payload.playlist_draft_id is not None:
            session.playlist_draft_id = payload.playlist_draft_id
        if payload.playlist_uri is not None:
            session.playlist_uri = payload.playlist_uri
        if payload.programmable_id is not None:
            session.programmable_id = payload.programmable_id
        if payload.ndef_payload_text is not None:
            session.ndef_payload_text = payload.ndef_payload_text
        if payload.ndef_payload_hex is not None:
            session.ndef_payload_hex = payload.ndef_payload_hex
        if payload.source_scan_dump_id is not None:
            session.source_scan_dump_id = payload.source_scan_dump_id
        if payload.verification_armed is not None:
            session.verification_armed = payload.verification_armed
        if payload.last_verification_event_id is not None:
            session.last_verification_event_id = payload.last_verification_event_id
        if payload.extra_json is not None:
            session.extra_json = payload.extra_json

    db.add(session)
    db.commit()
    db.refresh(session)
    return _build_card_programming_session_response(session)


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


@router.post("/programming-events", response_model=CardProgrammingEventResponse, status_code=201)
async def create_card_programming_event(
    payload: CardProgrammingEventCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> CardProgrammingEventResponse:
    card = db.get(PhysicalCard, payload.card_id) if payload.card_id is not None else None
    if payload.card_id is not None and card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    event = CardProgrammingEvent(
        card_id=payload.card_id,
        card_code=payload.card_code,
        event_type=payload.event_type,
        runtime=payload.runtime,
        source=payload.source,
        target_label=payload.target_label,
        detail=payload.detail,
        compared_field=payload.compared_field,
        matched=payload.matched,
        playlist_uri=payload.playlist_uri,
        programmable_id=payload.programmable_id,
        nfc_serial_number=payload.nfc_serial_number,
        ndef_payload_text=payload.ndef_payload_text,
        ndef_payload_hex=payload.ndef_payload_hex,
        observed_programmable_id=payload.observed_programmable_id,
        observed_nfc_serial_number=payload.observed_nfc_serial_number,
        observed_ndef_payload_text=payload.observed_ndef_payload_text,
        observed_ndef_payload_hex=payload.observed_ndef_payload_hex,
        extra_json=payload.extra_json,
    )
    db.add(event)

    if card is not None:
        now = datetime.now(UTC)
        previous_status = card.status
        previous_playlist_uri = card.yoto_playlist_uri
        if payload.card_code:
            card.card_code = payload.card_code
        if payload.runtime and not card.scan_source:
            card.scan_source = payload.runtime
        if payload.playlist_uri:
            card.yoto_playlist_uri = payload.playlist_uri
        if payload.programmable_id:
            card.programmable_id = payload.programmable_id
        if payload.nfc_serial_number:
            card.nfc_serial_number = payload.nfc_serial_number
        if payload.ndef_payload_text:
            card.ndef_payload_text = payload.ndef_payload_text
        if payload.ndef_payload_hex:
            card.ndef_payload_hex = payload.ndef_payload_hex

        if payload.event_type == "write_completed":
            card.ndef_prepared = True
            card.last_programmed_at = now
            if card.status == "available":
                card.status = "ready_to_link"
        elif payload.event_type in {"verification_succeeded", "verification_failed"}:
            card.last_scanned_at = now
            if payload.observed_programmable_id:
                card.programmable_id = payload.observed_programmable_id
            if payload.observed_nfc_serial_number:
                card.nfc_serial_number = payload.observed_nfc_serial_number
            if payload.observed_ndef_payload_text:
                card.ndef_payload_text = payload.observed_ndef_payload_text
            if payload.observed_ndef_payload_hex:
                card.ndef_payload_hex = payload.observed_ndef_payload_hex
            if payload.event_type == "verification_succeeded":
                card.ndef_prepared = True
                if card.status == "available":
                    card.status = "ready_to_link"

        db.add(card)
        db.add(
            CardAssignmentEvent(
                card_id=card.id,
                event_type="card_programming_event",
                previous_library_item_id=card.current_library_item_id,
                library_item_id=card.current_library_item_id,
                previous_status=previous_status,
                new_status=card.status,
                previous_yoto_playlist_uri=previous_playlist_uri,
                yoto_playlist_uri=card.yoto_playlist_uri,
                summary=f"Persisted programming event: {payload.event_type}",
            )
        )

    db.commit()
    db.refresh(event)

    logger.info("CARD_PROGRAMMING_EVENT %s", payload.model_dump_json())
    return _build_card_programming_event_response(event)


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


@router.get("/{card_id}/programming-events", response_model=list[CardProgrammingEventResponse])
async def list_card_programming_events_for_card(
    card_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[CardProgrammingEventResponse]:
    card = db.get(PhysicalCard, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    events = db.scalars(
        select(CardProgrammingEvent)
        .where(CardProgrammingEvent.card_id == card.id)
        .order_by(CardProgrammingEvent.created_at.desc(), CardProgrammingEvent.id.desc())
    )
    return [_build_card_programming_event_response(event) for event in events]


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
