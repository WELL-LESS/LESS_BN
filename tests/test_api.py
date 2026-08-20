from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def authenticate() -> tuple[dict[str, str], dict]:
    response = client.post(
        "/api/v1/auth/code/verify",
        json={"personal_code": "WHS-2026-1234", "device_id": "test-device"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}, data


def test_health_and_error_contract(monkeypatch) -> None:
    monkeypatch.setattr(settings, "supabase_secret_key", None)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"].startswith("req_")

    invalid = client.post(
        "/api/v1/auth/code/verify",
        json={"personal_code": "WRONG-CODE", "device_id": "test-device"},
    )
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "INVALID_PERSONAL_CODE"


def test_core_hackathon_flow(monkeypatch) -> None:
    # Keep the integration test deterministic even when a developer has local secrets.
    monkeypatch.setattr(settings, "supabase_secret_key", None)
    headers, auth_data = authenticate()

    overview = client.get("/api/v1/me/overview", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["data"]["latest_diagnosis"]["diagnosis_code"] == "OSP"

    diagnosis_id = auth_data["latest_diagnosis_id"]
    diagnosis = client.get(f"/api/v1/diagnoses/{diagnosis_id}", headers=headers)
    assert diagnosis.status_code == 200
    assert len(diagnosis.json()["data"]["metrics"]) == 6
    assert diagnosis.json()["data"]["images"] == []

    skin_types = client.get("/api/v1/skin-types", headers=headers)
    assert skin_types.status_code == 200
    assert [family["code"] for family in skin_types.json()["data"]] == ["O", "D", "C"]
    assert sum(len(family["types"]) for family in skin_types.json()["data"]) == 12

    categories = client.get("/api/v1/product-categories", headers=headers)
    assert categories.status_code == 200
    assert len(categories.json()["data"]) == 8

    created = client.post(
        "/api/v1/routines",
        headers=headers,
        json={
            "diagnosis_id": diagnosis_id,
            "category_codes": ["ESSENCE_SERUM_AMPOULE"],
        },
    )
    assert created.status_code == 201
    routine_id = created.json()["data"]["id"]

    uploaded = client.post(
        f"/api/v1/routines/{routine_id}/product-inputs",
        headers=headers,
        data={"category_code": "ESSENCE_SERUM_AMPOULE"},
        files={"images": ("serum.jpg", b"fake-jpeg-for-api-contract", "image/jpeg")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["data"]["status"] == "UPLOADED"

    composed = client.post(
        f"/api/v1/routines/{routine_id}/compose",
        headers={**headers, "Idempotency-Key": "compose-test-1"},
    )
    assert composed.status_code == 202
    job_id = composed.json()["data"]["id"]
    job = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert job.json()["data"]["status"] == "SUCCEEDED"

    routine = client.get(f"/api/v1/routines/{routine_id}", headers=headers).json()["data"]
    assert routine["status"] == "REVIEW_REQUIRED"
    reversed_items = [
        {"routine_item_id": item["id"], "position": position}
        for position, item in enumerate(reversed(routine["items"]), start=1)
    ]
    reordered = client.put(
        f"/api/v1/routines/{routine_id}/items/order",
        headers=headers,
        json={"items": reversed_items},
    )
    assert reordered.status_code == 200

    confirmed = client.post(f"/api/v1/routines/{routine_id}/confirm", headers=headers)
    assert confirmed.json()["data"]["status"] == "CONFIRMED"

    analyzed = client.post(
        f"/api/v1/routines/{routine_id}/suitability-analysis",
        headers={**headers, "Idempotency-Key": "analysis-test-1"},
    )
    assert analyzed.status_code == 202

    analysis = client.get(
        f"/api/v1/routines/{routine_id}/analysis",
        headers=headers,
    ).json()["data"]
    assert analysis["overall_score"] == 68
    recommendation = next(
        item["recommendation"] for item in analysis["items"] if item["recommendation"]
    )

    decision = client.put(
        f"/api/v1/routines/{routine_id}/recommendations/{recommendation['id']}/decision",
        headers={**headers, "Idempotency-Key": "decision-test-1"},
        json={"decision": "REPLACE"},
    )
    assert decision.status_code == 200
    assert decision.json()["data"]["status"] == "COMPLETED"

    cart = client.get("/api/v1/cart", headers=headers).json()["data"]
    assert cart["total_amount"] == 48000
    assert cart["items"][0]["product"]["brand"] == "AAC"

    order = client.post(
        "/api/v1/orders",
        headers={**headers, "Idempotency-Key": "order-test-1"},
        json={"payment_method": "KAKAO_PAY", "return_url": "wellless://orders/return"},
    )
    assert order.status_code == 201
    order_id = order.json()["data"]["id"]
    paid = client.get(f"/api/v1/orders/{order_id}", headers=headers)
    assert paid.json()["data"]["status"] == "PAID"

    history = client.get("/api/v1/routines?status=COMPLETED", headers=headers)
    assert any(item["id"] == routine_id for item in history.json()["data"])


def test_protected_endpoint_requires_token() -> None:
    response = client.get("/api/v1/me/overview")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
