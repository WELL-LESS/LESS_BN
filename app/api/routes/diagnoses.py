from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.services.store import store

router = APIRouter()


@router.get("/{diagnosis_id}")
async def get_diagnosis(diagnosis_id: str, session: SessionDependency) -> dict:
    return {"data": store.diagnosis(session, diagnosis_id)}
