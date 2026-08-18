from pydantic import BaseModel


class IntegrationStatusResponse(BaseModel):
    supabase_configured: bool
    openai_configured: bool
    openai_model: str

