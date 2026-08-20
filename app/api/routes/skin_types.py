from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.services.store import store

router = APIRouter()


@router.get("")
async def skin_types(_session: SessionDependency) -> dict:
    return {"data": store.skin_type_catalog(), "meta": {"next_cursor": None}}
