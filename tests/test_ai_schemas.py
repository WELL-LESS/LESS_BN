import pytest
from pydantic import ValidationError

from app.schemas.ai import SuitabilityAnalysisOutput


def test_suitability_output_is_strict_and_versioned() -> None:
    output = SuitabilityAnalysisOutput.model_validate(
        {
            "schema_version": "suitability-analysis-v1",
            "overall_score": 68,
            "summary": "현재 진단 기준으로 일부 제품을 덜어내는 편이 좋습니다.",
            "score_factors": [
                {"label": "자극 가능성", "delta": -22, "evidence": "에탄올 표기"}
            ],
            "products": [
                {
                    "scan_id": "scan-1",
                    "score": 22,
                    "verdict": "REMOVE",
                    "summary": "현재 피부 상태와 맞지 않을 수 있습니다.",
                    "factors": [
                        {"label": "주의 성분", "delta": -22, "evidence": "에탄올"}
                    ],
                    "caution_ingredients": ["에탄올"],
                    "confidence": 0.9,
                }
            ],
            "disclaimer": "본 결과는 의료 진단이 아닙니다.",
        }
    )

    assert output.overall_score == 68
    assert output.products[0].verdict == "REMOVE"


def test_suitability_output_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SuitabilityAnalysisOutput.model_validate(
            {
                "schema_version": "suitability-analysis-v1",
                "overall_score": 68,
                "summary": "요약",
                "score_factors": [],
                "products": [],
                "disclaimer": "의료 진단이 아닙니다.",
                "invented_product_id": "must-not-be-accepted",
            }
        )
