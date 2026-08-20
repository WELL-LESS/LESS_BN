import json

from fastapi.testclient import TestClient

from app.api.routes import ai_analysis
from app.main import app

client = TestClient(app)


async def _fake_product_analysis(**_kwargs) -> str:
    return json.dumps(
        {
            "status": "success",
            "product_analysis": {
                "product_name": "테스트 세럼",
                "category": "세럼",
                "analysis_summary": "진정 성분이 확인되었습니다.",
                "matched_primary_targets": [
                    {"ingredient": "나이아신아마이드", "ingredient_group_id": "NIACINAMIDE"}
                ],
                "optional_matches": [],
                "low_relevance_groups": [],
                "score_breakdown": {"final_score": 72},
            },
        },
        ensure_ascii=False,
    )


async def _fake_routine_analysis(**_kwargs) -> str:
    return json.dumps(
        {
            "status": "success",
            "ruleset_version": "LESS_SIX_INGREDIENTS_1.1",
            "routine_analysis": {
                "summary": "한 제품으로 구성된 테스트 루틴입니다.",
                "penalty_breakdown": {"final_score": 72},
                "remove_candidates": [],
            },
        },
        ensure_ascii=False,
    )


def test_analyze_routine_returns_app_view(monkeypatch) -> None:
    monkeypatch.setattr(ai_analysis, "run_product_image_prompt", _fake_product_analysis)
    monkeypatch.setattr(ai_analysis, "run_prompt", _fake_routine_analysis)

    response = client.post(
        "/api/v1/ai/analyze-routine",
        data={"profile_code": "O-S-P"},
        files={"images": ("serum.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["overall_score"] == 72
    assert data["products"][0]["name"] == "테스트 세럼"
    assert data["products"][0]["individual_score"] == 72
    assert data["routine"][0]["position"] == 1


def test_analyze_routine_rejects_non_image() -> None:
    response = client.post(
        "/api/v1/ai/analyze-routine",
        data={"profile_code": "O-S-P"},
        files={"images": ("notes.txt", b"not-image", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_IMAGE_TYPE"
