from fastapi import APIRouter, Response, status

from app.api.dependencies import SessionDependency
from app.schemas.api import CodeVerifyRequest, RefreshRequest
from app.services.store import store

router = APIRouter()


@router.post("/code/verify")
async def verify_code(payload: CodeVerifyRequest) -> dict:
    return {"data": store.verify_code(payload.personal_code, payload.device_id)}


@router.post("/token/refresh")
async def refresh_token(payload: RefreshRequest) -> dict:
    return {"data": store.refresh(payload.refresh_token)}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(session: SessionDependency) -> Response:
    store.revoke(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
