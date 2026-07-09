from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import CardAssignmentEvent, PhysicalCard
from app.schemas.foundation import CardAssignmentEventResponse, CardCreate, CardResponse


router = APIRouter()


def _build_card_response(card: PhysicalCard) -> CardResponse:
    return CardResponse(
        id=card.id,
        card_code=card.card_code,
        programmable_id=card.programmable_id,
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
        last_linked_at=card.last_linked_at,
        last_programmed_at=card.last_programmed_at,
        last_tested_at=card.last_tested_at,
        notes=card.notes,
        created_at=card.created_at,
    )


def _build_card_assignment_event_response(event: CardAssignmentEvent) -> CardAssignmentEventResponse:
    return CardAssignmentEventResponse.model_validate(event, from_attributes=True)


@router.get("", response_model=list[CardResponse])
async def list_cards(db: Annotated[Session, Depends(get_db_session)]) -> list[CardResponse]:
    query = select(PhysicalCard).order_by(PhysicalCard.card_code.asc(), PhysicalCard.id.asc())
    return [_build_card_response(card) for card in db.scalars(query)]


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
    card = PhysicalCard(**payload.model_dump())
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
