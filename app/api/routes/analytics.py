from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.schemas.api import AnalyticsBatchRequest
from app.services.store import store

router = APIRouter()


@router.post("/events/batch")
async def ingest_events(payload: AnalyticsBatchRequest, session: SessionDependency) -> dict:
    for event in payload.events:
        store.record_event(
            session,
            event.name,
            event.properties,
            event.occurred_at.isoformat(),
        )
    return {"data": {"accepted": len(payload.events)}}
