from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.models import Job
from app.schemas.foundation import JobResponse


router = APIRouter()


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    db: Annotated[Session, Depends(get_db_session)],
    include_pending_delete: bool = False,
) -> list[JobResponse]:
    query = select(Job).order_by(Job.created_at.desc(), Job.id.desc())
    if not include_pending_delete:
        query = query.where(Job.pending_delete.is_(False))
    jobs = db.scalars(query)
    return [JobResponse.model_validate(job, from_attributes=True) for job in jobs]


@router.post("/{job_id}/retry", response_model=JobResponse)
async def retry_job(
    job_id: int,
    db: Annotated[Session, Depends(get_db_session)],
) -> JobResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.retry_count >= job.max_retries:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Max retries reached")

    job.status = "queued"
    job.retry_count += 1
    job.progress_percent = 0
    job.progress_message = "Queued for retry"
    job.error_summary = None
    job.error_detail = None
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobResponse.model_validate(job, from_attributes=True)
