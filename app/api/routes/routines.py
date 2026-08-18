from fastapi import APIRouter

from app.schemas.routine import RoutineAnalysisRequest, RoutineAnalysisResponse
from app.services.analysis import analyze_routine

router = APIRouter()


@router.post("/analyze", response_model=RoutineAnalysisResponse)
async def analyze(payload: RoutineAnalysisRequest) -> RoutineAnalysisResponse:
    return analyze_routine(payload)

