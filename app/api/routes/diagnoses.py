from fastapi import APIRouter, HTTPException, status

from app.schemas.diagnosis import DiagnosisResponse
from app.services.demo_data import DEMO_DIAGNOSIS

router = APIRouter()


@router.get("/{diagnosis_id}", response_model=DiagnosisResponse)
async def get_diagnosis(diagnosis_id: str) -> DiagnosisResponse:
    if diagnosis_id != DEMO_DIAGNOSIS.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="피부 진단 결과를 찾을 수 없습니다.",
        )
    return DEMO_DIAGNOSIS

