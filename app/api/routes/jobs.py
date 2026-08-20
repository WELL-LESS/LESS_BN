from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.services.store import store

router = APIRouter()


@router.get("/{job_id}")
async def get_job(job_id: str, session: SessionDependency) -> dict:
    return {"data": store.get_job(session, job_id)}
