"""Versioned structured-output contracts for OpenAI analysis.

The model may describe and score only the supplied scan IDs. Database IDs,
prices, and the final AAC replacement product are selected by the backend.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictAiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IngredientEvidence(StrictAiModel):
    name: str = Field(min_length=1, max_length=200)
    normalized_name: str | None = Field(default=None, max_length=200)
    evidence: str = Field(min_length=1, max_length=500)


class ProductIdentification(StrictAiModel):
    scan_id: str
    brand: str | None = Field(default=None, max_length=200)
    product_name: str = Field(min_length=1, max_length=300)
    category_code: str
    ingredients: list[IngredientEvidence]
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)


class ProductIdentificationOutput(StrictAiModel):
    schema_version: Literal["product-identification-v1"]
    products: list[ProductIdentification]


class RoutineCompositionItem(StrictAiModel):
    scan_id: str
    position: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


class RoutineCompositionOutput(StrictAiModel):
    schema_version: Literal["routine-composition-v1"]
    items: list[RoutineCompositionItem]
    warnings: list[str] = Field(default_factory=list)


class ScoreFactor(StrictAiModel):
    label: str = Field(min_length=1, max_length=100)
    delta: int = Field(ge=-100, le=100)
    evidence: str = Field(min_length=1, max_length=500)


class ProductSuitability(StrictAiModel):
    scan_id: str
    score: int = Field(ge=0, le=100)
    verdict: Literal["KEEP", "CHOICE", "REMOVE"]
    summary: str = Field(min_length=1, max_length=500)
    factors: list[ScoreFactor]
    caution_ingredients: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class SuitabilityAnalysisOutput(StrictAiModel):
    schema_version: Literal["suitability-analysis-v1"]
    overall_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=1000)
    score_factors: list[ScoreFactor]
    products: list[ProductSuitability]
    disclaimer: str = Field(min_length=1, max_length=500)
