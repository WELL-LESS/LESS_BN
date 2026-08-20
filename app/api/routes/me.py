from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.services.store import store

router = APIRouter()


@router.get("/overview")
async def overview(session: SessionDependency) -> dict:
    return {"data": store.overview(session)}
