from pydantic import BaseModel


class DiagnosisResponse(BaseModel):
    id: str
    skin_type: str
    concerns: list[str]
    recommended_ingredients: list[str]
    caution_ingredients: list[str]

