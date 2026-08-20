from enum import StrEnum

from pydantic import BaseModel, Field


class UsageTime(StrEnum):
    morning = "MORNING"
    night = "NIGHT"
    both = "MORNING_AND_NIGHT"


class ProductStatus(StrEnum):
    keep = "KEEP"
    caution = "CAUTION"
    replace = "REPLACE"


class RoutineProductInput(BaseModel):
    product_id: str
    name: str
    category: str
    ingredients: list[str] = Field(default_factory=list)
    usage: UsageTime = UsageTime.both


class RoutineAnalysisRequest(BaseModel):
    diagnosis_id: str
    products: list[RoutineProductInput] = Field(min_length=1)


class RoutineStep(BaseModel):
    order: int
    product_id: str
    name: str
    category: str


class ProductAnalysisResult(BaseModel):
    product_id: str
    score: int = Field(ge=0, le=100)
    status: ProductStatus
    reasons: list[str]
    replacement_product_id: str | None = None


class RoutineAnalysisResponse(BaseModel):
    analysis_id: str
    overall_score: int = Field(ge=0, le=100)
    morning_routine: list[RoutineStep]
    night_routine: list[RoutineStep]
    product_results: list[ProductAnalysisResult]
    disclaimer: str
