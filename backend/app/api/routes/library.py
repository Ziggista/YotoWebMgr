from typing import Annotated
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models import ImportRequest, LibraryItem, User
from app.schemas.foundation import LibraryItemCreate, LibraryItemResponse


router = APIRouter()


def _is_allowed_media_path(path: Path) -> bool:
    settings = get_settings()
    allowed_roots = [
        Path(settings.import_drop_path).resolve(strict=False),
        Path(settings.browser_upload_path).resolve(strict=False),
    ]
    resolved = path.resolve(strict=False)
    return any(resolved == root or root in resolved.parents for root in allowed_roots)


def _media_url_for_item(db: Session, item: LibraryItem) -> str | None:
    if item.source_import_id is None:
        return None
    import_request = db.get(ImportRequest, item.source_import_id)
    if not import_request or not import_request.source_path:
        return None
    source_path = Path(import_request.source_path)
    if not _is_allowed_media_path(source_path) or not source_path.exists():
        return None
    return f"/api/v1/library/{item.id}/media"


def _build_library_item_response(db: Session, item: LibraryItem) -> LibraryItemResponse:
    return LibraryItemResponse(
        id=item.id,
        title=item.title,
        content_type=item.content_type,
        status=item.status,
        notes=item.notes,
        created_at=item.created_at,
        media_url=_media_url_for_item(db, item),
    )


@router.get("", response_model=list[LibraryItemResponse])
async def list_library_items(
    db: Annotated[Session, Depends(get_db_session)],
    content_type: str | None = None,
) -> list[LibraryItemResponse]:
    query = select(LibraryItem).order_by(LibraryItem.created_at.desc(), LibraryItem.id.desc())
    if content_type:
        query = query.where(LibraryItem.content_type == content_type)
    return [_build_library_item_response(db, item) for item in db.scalars(query)]


@router.get("/{item_id}/media")
async def get_library_item_media(
    item_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> FileResponse:
    item = db.get(LibraryItem, item_id)
    if item is None or item.source_import_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")
    import_request = db.get(ImportRequest, item.source_import_id)
    if import_request is None or not import_request.source_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    source_path = Path(import_request.source_path)
    if not _is_allowed_media_path(source_path) or not source_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    return FileResponse(source_path)


@router.post("", response_model=LibraryItemResponse, status_code=201)
async def create_library_item(
    payload: LibraryItemCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> LibraryItemResponse:
    owner = None
    if payload.owner_user_slug:
        owner = db.scalar(select(User).where(User.slug == payload.owner_user_slug))

    item = LibraryItem(
        title=payload.title,
        content_type=payload.content_type,
        status="draft",
        notes=payload.notes,
        owner_user_id=owner.id if owner else None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _build_library_item_response(db, item)
