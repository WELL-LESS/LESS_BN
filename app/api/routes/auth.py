from fastapi import APIRouter, HTTPException, status

from app.schemas.auth import CodeAuthRequest, CodeAuthResponse
from app.services.demo_data import DEMO_PERSONAL_CODE

router = APIRouter()


@router.post("/code", response_model=CodeAuthResponse)
async def authenticate_code(payload: CodeAuthRequest) -> CodeAuthResponse:
    if payload.personal_code != DEMO_PERSONAL_CODE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 개인 코드입니다.",
        )
    return CodeAuthResponse(user_id="demo-user", diagnosis_id="demo-diagnosis")

