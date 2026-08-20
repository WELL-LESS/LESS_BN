from pydantic import BaseModel, Field


class CodeAuthRequest(BaseModel):
    personal_code: str = Field(min_length=4, max_length=32)


class CodeAuthResponse(BaseModel):
    user_id: str
    diagnosis_id: str
