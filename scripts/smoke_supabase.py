"""Run the core API flow against configured Supabase and clean transient test data."""

import hashlib

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.store import store
from app.services.supabase_client import get_supabase_admin_client


def require_success(response, step: str) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"{step} failed ({response.status_code}): {response.text}")
    body = response.json()
    return body.get("data", body)


def main() -> None:
    if not settings.has_supabase_config:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    api = TestClient(app)
    admin = get_supabase_admin_client()
    access_token = None
    session_id = None
    routine_id = None
    cart_ids: list[str] = []
    storage_paths: list[str] = []

    try:
        auth = require_success(
            api.post(
                "/api/v1/auth/code/verify",
                json={"personal_code": "WHS-2026-1234", "device_id": "supabase-smoke"},
            ),
            "authenticate",
        )
        access_token = auth["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        session_id = (
            admin.table("access_sessions")
            .select("id")
            .eq("access_token_hash", token_hash)
            .limit(1)
            .execute()
            .data[0]["id"]
        )

        diagnosis = require_success(
            api.get(f"/api/v1/diagnoses/{auth['latest_diagnosis_id']}", headers=headers),
            "diagnosis",
        )
        categories = require_success(
            api.get("/api/v1/product-categories", headers=headers),
            "categories",
        )
        routine = require_success(
            api.post(
                "/api/v1/routines",
                headers=headers,
                json={
                    "diagnosis_id": auth["latest_diagnosis_id"],
                    "category_codes": ["ESSENCE_SERUM_AMPOULE"],
                },
            ),
            "create routine",
        )
        routine_id = routine["id"]

        product_input = require_success(
            api.post(
                f"/api/v1/routines/{routine_id}/product-inputs",
                headers=headers,
                data={"category_code": "ESSENCE_SERUM_AMPOULE"},
                files={"images": ("smoke.jpg", b"well-less-smoke", "image/jpeg")},
            ),
            "upload product",
        )
        storage_paths.extend(image["object_path"] for image in product_input["images"])
        session = store.get_session(access_token)
        if session is None:
            raise RuntimeError("created session could not be loaded")
        ai_run = store.record_ai_analysis_result(
            session,
            routine_id,
            input_payload={"profile_code": diagnosis["diagnosis_code"], "image_count": 1},
            output_payload={
                "overall_score": 73,
                "summary": "Supabase smoke analysis",
                "ruleset_version": "smoke-v1",
            },
        )
        linked_images = (
            admin.table("ai_analysis_run_images")
            .select("product_scan_image_id")
            .eq("ai_analysis_run_id", ai_run["id"])
            .execute()
            .data
        )
        if len(linked_images) != 1:
            raise RuntimeError(f"unexpected linked image count: {len(linked_images)}")
        require_success(
            api.post(f"/api/v1/routines/{routine_id}/compose", headers=headers),
            "compose",
        )
        require_success(
            api.post(f"/api/v1/routines/{routine_id}/confirm", headers=headers),
            "confirm",
        )
        require_success(
            api.post(f"/api/v1/routines/{routine_id}/suitability-analysis", headers=headers),
            "analyze",
        )
        analysis = require_success(
            api.get(f"/api/v1/routines/{routine_id}/analysis", headers=headers),
            "get analysis",
        )
        recommendation = next(
            item["recommendation"] for item in analysis["items"] if item["recommendation"]
        )
        require_success(
            api.put(
                f"/api/v1/routines/{routine_id}/recommendations/{recommendation['id']}/decision",
                headers=headers,
                json={"decision": "REPLACE"},
            ),
            "replace",
        )
        cart = require_success(api.get("/api/v1/cart", headers=headers), "cart")
        if cart["total_amount"] != 48000:
            raise RuntimeError(f"unexpected cart total: {cart['total_amount']}")
        order = require_success(
            api.post(
                "/api/v1/orders",
                headers=headers,
                json={
                    "payment_method": "KAKAO_PAY",
                    "return_url": "wellless://orders/return",
                },
            ),
            "create order",
        )
        paid = require_success(
            api.get(f"/api/v1/orders/{order['id']}", headers=headers),
            "complete mock payment",
        )
        if paid["status"] != "PAID":
            raise RuntimeError(f"unexpected payment status: {paid['status']}")
        print(
            "Supabase smoke passed:",
            f"skin={diagnosis['diagnosis_code']}",
            f"categories={len(categories)}",
            f"score={analysis['overall_score']}",
            f"payment={paid['status']}",
        )
    finally:
        if routine_id:
            cart_ids = [
                row["id"]
                for row in admin.table("carts")
                .select("id")
                .eq("routine_id", routine_id)
                .execute()
                .data
            ]
            admin.table("analytics_events").delete().eq("routine_id", routine_id).execute()
            admin.table("orders").delete().eq("routine_id", routine_id).execute()
            for cart_id in cart_ids:
                admin.table("carts").delete().eq("id", cart_id).execute()
            admin.table("routine_sessions").delete().eq("id", routine_id).execute()
        if storage_paths:
            admin.storage.from_("product-scans-original").remove(storage_paths)
        if session_id:
            admin.table("analytics_events").delete().eq("access_session_id", session_id).execute()
            admin.table("access_sessions").delete().eq("id", session_id).execute()


if __name__ == "__main__":
    main()
