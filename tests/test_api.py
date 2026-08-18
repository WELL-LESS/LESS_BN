from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_integration_status_without_secrets() -> None:
    response = client.get("/api/v1/integrations/status")
    assert response.status_code == 200
    assert response.json() == {
        "supabase_configured": False,
        "openai_configured": False,
        "openai_model": "gpt-5.6-luna",
    }


def test_demo_code_authentication() -> None:
    response = client.post("/api/v1/auth/code", json={"personal_code": "AAC2026"})
    assert response.status_code == 200
    assert response.json()["diagnosis_id"] == "demo-diagnosis"


def test_routine_analysis_recommends_replacement() -> None:
    response = client.post(
        "/api/v1/routines/analyze",
        json={
            "diagnosis_id": "demo-diagnosis",
            "products": [
                {
                    "product_id": "product-1",
                    "name": "Demo Serum",
                    "category": "SERUM",
                    "ingredients": ["fragrance", "denatured alcohol"],
                    "usage": "MORNING_AND_NIGHT",
                }
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["overall_score"] == 40
    assert body["product_results"][0]["status"] == "REPLACE"
    assert body["product_results"][0]["replacement_product_id"] == "aac-serum-001"
