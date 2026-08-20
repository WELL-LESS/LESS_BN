from fastapi import APIRouter

from app.api.dependencies import SessionDependency
from app.services.store import store

router = APIRouter()


@router.get("")
async def product_categories(_session: SessionDependency) -> dict:
    return {"data": store.get_categories(), "meta": {"next_cursor": None}}
