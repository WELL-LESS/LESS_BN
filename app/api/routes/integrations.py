from fastapi import APIRouter

from app.core.config import settings
from app.schemas.integrations import IntegrationStatusResponse

router = APIRouter()


@router.get("/status", response_model=IntegrationStatusResponse)
async def integration_status() -> IntegrationStatusResponse:
    return IntegrationStatusResponse(
        supabase_configured=settings.has_supabase_config,
        openai_configured=settings.has_openai_config,
        openai_model=settings.openai_model,
    )
