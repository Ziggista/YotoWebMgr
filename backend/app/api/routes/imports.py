from typing import Annotated
from datetime import UTC, datetime
from pathlib import Path
from re import sub
from uuid import uuid4
import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models import ImportRequest, Job, LibraryItem, PlaylistTrack, User
from app.schemas.foundation import ImportCreate, ImportResponse, ImportReviewApprove, ImportReviewUpdate, ImportSourceInfo


router = APIRouter()
allowed_audio_extensions = [
    ".aac",
    ".flac",
    ".m4a",
    ".m4b",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
]
allowed_import_extensions = [*allowed_audio_extensions, ".zip"]


def _normalise_filesystem_source(source_path: str | None) -> str:
    if not source_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filesystem imports require a source path.",
        )

    _ensure_import_directories()
    settings = get_settings()
    drop_root = Path(settings.import_drop_path).resolve(strict=False)
    candidate = Path(source_path)
    if not candidate.is_absolute():
        candidate = drop_root / candidate
    resolved = candidate.resolve(strict=False)

    if resolved != drop_root and drop_root not in resolved.parents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Filesystem imports must live under {drop_root}.",
        )

    return str(resolved)


def _safe_upload_filename(filename: str) -> str:
    source_name = Path(filename).name
    stem = sub(r"[^A-Za-z0-9._-]+", "-", Path(source_name).stem).strip(".-")
    suffix = Path(source_name).suffix.lower()
    if suffix not in allowed_import_extensions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported import extension: {suffix or 'none'}.",
        )
    return f"{stem or 'upload'}-{uuid4().hex[:12]}{suffix}"


def _title_from_track_path(path: Path) -> str:
    cleaned = sub(r"^[0-9]+[\s._-]+", "", path.stem)
    cleaned = sub(r"[\s._-]+", " ", cleaned).strip()
    return cleaned or path.stem


def _extract_zip_upload(zip_path: Path, upload_root: Path) -> list[Path]:
    extract_root = upload_root / f"{zip_path.stem}-extracted"
    extract_root.mkdir(parents=True, exist_ok=True)
    audio_files: list[Path] = []

    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            member_path = Path(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise HTTPException(status_code=422, detail="ZIP import contains an unsafe path.")
            if member_path.suffix.lower() not in allowed_audio_extensions:
                continue
            destination = (extract_root / member_path).resolve(strict=False)
            if extract_root.resolve(strict=False) not in destination.parents:
                raise HTTPException(status_code=422, detail="ZIP import contains an unsafe path.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source_file, destination.open("wb") as output_file:
                while chunk := source_file.read(1024 * 1024):
                    output_file.write(chunk)
            audio_files.append(destination)

    if not audio_files:
        raise HTTPException(status_code=422, detail="ZIP import did not contain supported audio files.")
    return sorted(audio_files, key=lambda path: str(path.relative_to(extract_root)).lower())


def _ensure_import_directories() -> None:
    settings = get_settings()
    Path(settings.import_drop_path).mkdir(parents=True, exist_ok=True)
    Path(settings.browser_upload_path).mkdir(parents=True, exist_ok=True)


def _build_import_response(db: Session, import_request: ImportRequest) -> ImportResponse:
    library_item = db.scalar(
        select(LibraryItem).where(LibraryItem.source_import_id == import_request.id)
    )
    job = db.scalar(select(Job).where(Job.related_import_id == import_request.id))
    return ImportResponse(
        id=import_request.id,
        title=import_request.title,
        source_type=import_request.source_type,
        source_path=import_request.source_path,
        content_type=import_request.content_type,
        status=import_request.status,
        review_status=import_request.review_status,
        review_notes=import_request.review_notes,
        reviewed_at=import_request.reviewed_at,
        approved_at=import_request.approved_at,
        pending_delete=import_request.pending_delete,
        created_at=import_request.created_at,
        related_library_item_id=library_item.id if library_item else None,
        related_job_id=job.id if job else None,
    )


def _create_import_records(
    db: Session,
    payload: ImportCreate,
    *,
    source_path: str | None = None,
    job_type: str | None = None,
    job_message: str = "Queued for media inspection",
    playlist_tracks: list[Path] | None = None,
) -> ImportResponse:
    requested_by = None
    if payload.requested_by_user_slug:
        requested_by = db.scalar(select(User).where(User.slug == payload.requested_by_user_slug))

    normalised_source_path = source_path if source_path is not None else payload.source_path
    if payload.source_type == "filesystem":
        normalised_source_path = _normalise_filesystem_source(payload.source_path)

    import_request = ImportRequest(
        title=payload.title,
        source_type=payload.source_type,
        source_path=normalised_source_path,
        content_type=payload.content_type,
        status="queued",
        requested_by_user_id=requested_by.id if requested_by else None,
    )
    db.add(import_request)
    db.flush()

    library_item = LibraryItem(
        title=payload.title,
        content_type=payload.content_type,
        status="import_queued",
        owner_user_id=requested_by.id if requested_by else None,
        source_import_id=import_request.id,
    )
    db.add(library_item)
    db.flush()

    resolved_job_type = (
        job_type
        if job_type is not None
        else "import_from_filesystem"
        if payload.source_type == "filesystem"
        else "inspect_media"
    )
    job = Job(
        type=resolved_job_type,
        status="queued",
        created_by_user_id=requested_by.id if requested_by else None,
        progress_percent=0,
        progress_message=job_message,
        related_import_id=import_request.id,
        related_library_item_id=library_item.id,
    )
    db.add(job)

    if playlist_tracks:
        for index, track_path in enumerate(playlist_tracks, start=1):
            db.add(
                PlaylistTrack(
                    library_item_id=library_item.id,
                    title=_title_from_track_path(track_path),
                    source_path=str(track_path),
                    track_number=index,
                    track_behavior="continue",
                )
            )
    db.commit()
    db.refresh(import_request)

    return ImportResponse(
        id=import_request.id,
        title=import_request.title,
        source_type=import_request.source_type,
        source_path=import_request.source_path,
        content_type=import_request.content_type,
        status=import_request.status,
        review_status=import_request.review_status,
        review_notes=import_request.review_notes,
        reviewed_at=import_request.reviewed_at,
        approved_at=import_request.approved_at,
        pending_delete=import_request.pending_delete,
        created_at=import_request.created_at,
        related_library_item_id=library_item.id,
        related_job_id=job.id,
    )


@router.get("/sources", response_model=ImportSourceInfo)
async def get_import_sources() -> ImportSourceInfo:
    _ensure_import_directories()
    settings = get_settings()
    return ImportSourceInfo(
        filesystem_drop_path=settings.import_drop_path,
        browser_upload_path=settings.browser_upload_path,
        allowed_extensions=allowed_import_extensions,
    )


@router.get("", response_model=list[ImportResponse])
async def list_imports(
    db: Annotated[Session, Depends(get_db_session)],
    include_pending_delete: bool = False,
) -> list[ImportResponse]:
    query = select(ImportRequest).order_by(ImportRequest.created_at.desc(), ImportRequest.id.desc())
    if not include_pending_delete:
        query = query.where(ImportRequest.pending_delete.is_(False))
    imports = db.scalars(query)
    return [_build_import_response(db, import_request) for import_request in imports]


@router.post("", response_model=ImportResponse, status_code=201)
async def create_import(
    payload: ImportCreate,
    db: Annotated[Session, Depends(get_db_session)],
) -> ImportResponse:
    return _create_import_records(db, payload)


@router.put("/{import_id}/review", response_model=ImportResponse)
async def update_import_review(
    import_id: int,
    payload: ImportReviewUpdate,
    db: Annotated[Session, Depends(get_db_session)],
) -> ImportResponse:
    import_request = db.get(ImportRequest, import_id)
    if import_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    reviewer = None
    if payload.reviewed_by_user_slug:
        reviewer = db.scalar(select(User).where(User.slug == payload.reviewed_by_user_slug))

    library_item = db.scalar(select(LibraryItem).where(LibraryItem.source_import_id == import_request.id))
    if payload.title is not None:
        import_request.title = payload.title
        if library_item is not None:
            library_item.title = payload.title
    if payload.content_type is not None:
        import_request.content_type = payload.content_type
        if library_item is not None:
            library_item.content_type = payload.content_type
    import_request.review_notes = payload.review_notes
    import_request.review_status = "reviewed"
    import_request.reviewed_at = datetime.now(UTC)
    import_request.reviewed_by_user_id = reviewer.id if reviewer else None
    db.add(import_request)
    if library_item is not None:
        db.add(library_item)
    db.commit()
    db.refresh(import_request)
    return _build_import_response(db, import_request)


@router.post("/{import_id}/approve", response_model=ImportResponse)
async def approve_import_review(
    import_id: int,
    payload: ImportReviewApprove,
    db: Annotated[Session, Depends(get_db_session)],
) -> ImportResponse:
    import_request = db.get(ImportRequest, import_id)
    if import_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    approver = None
    if payload.approved_by_user_slug:
        approver = db.scalar(select(User).where(User.slug == payload.approved_by_user_slug))

    import_request.review_status = "approved"
    import_request.approved_at = datetime.now(UTC)
    import_request.approved_by_user_id = approver.id if approver else None
    db.add(import_request)
    db.commit()
    db.refresh(import_request)
    return _build_import_response(db, import_request)


@router.post("/{import_id}/hide", response_model=ImportResponse)
async def hide_import(
    import_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> ImportResponse:
    import_request = db.get(ImportRequest, import_id)
    if import_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import not found")

    import_request.pending_delete = True
    import_request.status = "pending_delete"

    related_jobs = db.scalars(select(Job).where(Job.related_import_id == import_request.id))
    for job in related_jobs:
        job.pending_delete = True
        job.progress_message = "Hidden and ready for deletion"
        db.add(job)

    db.add(import_request)
    db.commit()
    db.refresh(import_request)
    return _build_import_response(db, import_request)


@router.post("/uploads", response_model=ImportResponse, status_code=201)
async def upload_import(
    db: Annotated[Session, Depends(get_db_session)],
    title: Annotated[str, File(min_length=1, max_length=240)],
    content_type: Annotated[str, File()],
    requested_by_user_slug: Annotated[str | None, File()] = None,
    media_file: UploadFile = File(...),
) -> ImportResponse:
    if not media_file.filename:
        raise HTTPException(status_code=422, detail="Upload requires a filename.")

    _ensure_import_directories()
    settings = get_settings()
    upload_root = Path(settings.browser_upload_path).resolve(strict=False)
    destination = upload_root / _safe_upload_filename(media_file.filename)

    with destination.open("wb") as output_file:
        while chunk := await media_file.read(1024 * 1024):
            output_file.write(chunk)

    extracted_tracks: list[Path] | None = None
    import_source_path = str(destination)
    job_type = None
    job_message = "Queued for media inspection"
    if destination.suffix.lower() == ".zip":
        extracted_tracks = _extract_zip_upload(destination, upload_root)
        import_source_path = str(upload_root / f"{destination.stem}-extracted")
        job_type = "extract_zip_import"
        job_message = f"Queued ZIP album import with {len(extracted_tracks)} discovered track(s)"

    payload = ImportCreate(
        title=title,
        source_type="browser_upload",
        source_path=import_source_path,
        content_type=content_type,
        requested_by_user_slug=requested_by_user_slug or None,
    )
    return _create_import_records(
        db,
        payload,
        source_path=import_source_path,
        job_type=job_type,
        job_message=job_message,
        playlist_tracks=extracted_tracks,
    )
