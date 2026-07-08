from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import LibraryItem, Tag, TagAssignment
from app.schemas.foundation import TagAssignmentUpdate, TagCreate, TagResponse


router = APIRouter()


def normalize_tag_name(name: str) -> str:
    return " ".join(name.casefold().strip().split())


def _tag_usage_subquery():
    return (
        select(TagAssignment.tag_id, func.count(TagAssignment.id).label("usage_count"))
        .group_by(TagAssignment.tag_id)
        .subquery()
    )


def _build_tag_response(tag: Tag, usage_count: int = 0) -> TagResponse:
    return TagResponse(
        id=tag.id,
        name=tag.name,
        normalized_name=tag.normalized_name,
        color=tag.color,
        usage_count=usage_count,
        created_at=tag.created_at,
    )


@router.get("", response_model=list[TagResponse])
async def list_tags(db: Annotated[Session, Depends(get_db_session)]) -> list[TagResponse]:
    usage = _tag_usage_subquery()
    rows = db.execute(
        select(Tag, func.coalesce(usage.c.usage_count, 0))
        .outerjoin(usage, usage.c.tag_id == Tag.id)
        .order_by(Tag.name.asc())
    ).all()
    return [_build_tag_response(tag, usage_count) for tag, usage_count in rows]


@router.post("", response_model=TagResponse, status_code=201)
async def create_tag(
    payload: TagCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> TagResponse:
    normalized_name = normalize_tag_name(payload.name)
    if not normalized_name:
        raise HTTPException(status_code=422, detail="Tag name cannot be blank.")

    tag = Tag(name=payload.name.strip(), normalized_name=normalized_name, color=payload.color)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        existing = db.scalar(select(Tag).where(Tag.normalized_name == normalized_name))
        if existing is not None:
            return _build_tag_response(existing)
        raise HTTPException(status_code=409, detail="Tag already exists.") from error
    db.refresh(tag)
    return _build_tag_response(tag)


@router.get("/library-items/{item_id}", response_model=list[TagResponse])
async def list_library_item_tags(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[TagResponse]:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")
    rows = db.scalars(
        select(Tag)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(TagAssignment.entity_type == "library_item")
        .where(TagAssignment.entity_id == item.id)
        .order_by(Tag.name.asc())
    )
    return [_build_tag_response(tag) for tag in rows]


@router.put("/library-items/{item_id}", response_model=list[TagResponse])
async def set_library_item_tags(
    item_id: int,
    payload: TagAssignmentUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> list[TagResponse]:
    item = db.get(LibraryItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library item not found")

    tag_ids = sorted(set(payload.tag_ids))
    if tag_ids:
        existing_count = db.scalar(select(func.count(Tag.id)).where(Tag.id.in_(tag_ids)))
        if existing_count != len(tag_ids):
            raise HTTPException(status_code=422, detail="One or more tags do not exist.")

    db.execute(
        delete(TagAssignment)
        .where(TagAssignment.entity_type == "library_item")
        .where(TagAssignment.entity_id == item.id)
    )
    for tag_id in tag_ids:
        db.add(TagAssignment(tag_id=tag_id, entity_type="library_item", entity_id=item.id))
    db.commit()
    return await list_library_item_tags(item.id, db)
