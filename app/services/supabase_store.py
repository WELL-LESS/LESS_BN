from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from app.core.errors import ApiError
from app.services.demo_store import DISCLAIMER, DemoSession, DemoStore, iso, utc_now
from app.services.supabase_client import get_supabase_admin_client


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class SupabaseStore:
    """Supabase-backed implementation of the API v1 application store."""

    allowed_events = DemoStore.allowed_events

    @property
    def client(self):
        return get_supabase_admin_client()

    def verify_code(self, personal_code: str, device_id: str) -> dict:
        now = utc_now()
        response = (
            self.client.table("diagnosis_codes")
            .select("id,is_active,expires_at")
            .eq("code_hash", _hash(personal_code.strip()))
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(
                401,
                "INVALID_PERSONAL_CODE",
                "개인 코드를 확인해주세요.",
                field="personal_code",
            )
        code = response.data[0]
        expires_at = _parse_datetime(code["expires_at"])
        if not code["is_active"] or (expires_at and expires_at <= now):
            raise ApiError(401, "EXPIRED_PERSONAL_CODE", "만료된 개인 코드입니다.")

        diagnosis_response = (
            self.client.table("skin_diagnoses")
            .select("id")
            .eq("diagnosis_code_id", code["id"])
            .order("diagnosed_at", desc=True)
            .limit(1)
            .execute()
        )
        if not diagnosis_response.data:
            raise ApiError(404, "DIAGNOSIS_NOT_FOUND", "피부 진단 결과를 찾을 수 없습니다.")

        session = self._create_session(code["id"], device_id)
        self.client.table("diagnosis_codes").update({"last_verified_at": iso(now)}).eq(
            "id", code["id"]
        ).execute()
        self.record_event(session, "code_verified", {})
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {"id": code["id"], "display_name": "사용자"},
            "latest_diagnosis_id": diagnosis_response.data[0]["id"],
        }

    def _create_session(self, diagnosis_code_id: str, device_id: str | None) -> DemoSession:
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(40)
        now = utc_now()
        expires_at = now + timedelta(hours=1)
        refresh_expires_at = now + timedelta(days=7)
        payload = {
            "diagnosis_code_id": diagnosis_code_id,
            "access_token_hash": _hash(access_token),
            "refresh_token_hash": _hash(refresh_token),
            "device_id_hash": _hash(device_id) if device_id else None,
            "expires_at": iso(expires_at),
            "refresh_expires_at": iso(refresh_expires_at),
        }
        created = self.client.table("access_sessions").insert(payload).execute().data[0]
        return DemoSession(
            id=created["id"],
            diagnosis_code_id=diagnosis_code_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    def get_session(self, access_token: str) -> DemoSession | None:
        response = (
            self.client.table("access_sessions")
            .select("id,diagnosis_code_id,expires_at,refresh_expires_at,revoked_at")
            .eq("access_token_hash", _hash(access_token))
            .limit(1)
            .execute()
        )
        if not response.data:
            return None
        row = response.data[0]
        expires_at = _parse_datetime(row["expires_at"])
        refresh_expires_at = _parse_datetime(row["refresh_expires_at"])
        revoked_at = _parse_datetime(row["revoked_at"])
        if revoked_at or expires_at is None or expires_at <= utc_now():
            return None
        self.client.table("access_sessions").update({"last_used_at": iso(utc_now())}).eq(
            "id", row["id"]
        ).execute()
        return DemoSession(
            id=row["id"],
            diagnosis_code_id=row["diagnosis_code_id"],
            access_token=access_token,
            refresh_token="",
            expires_at=expires_at,
            refresh_expires_at=refresh_expires_at or expires_at,
            revoked_at=revoked_at,
        )

    def refresh(self, refresh_token: str) -> dict:
        response = (
            self.client.table("access_sessions")
            .select("id,diagnosis_code_id,refresh_expires_at,revoked_at")
            .eq("refresh_token_hash", _hash(refresh_token))
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(401, "REFRESH_TOKEN_EXPIRED", "다시 개인 코드를 입력해주세요.")
        row = response.data[0]
        refresh_expires_at = _parse_datetime(row["refresh_expires_at"])
        if row["revoked_at"] or refresh_expires_at is None or refresh_expires_at <= utc_now():
            raise ApiError(401, "REFRESH_TOKEN_EXPIRED", "다시 개인 코드를 입력해주세요.")
        self.client.table("access_sessions").update({"revoked_at": iso(utc_now())}).eq(
            "id", row["id"]
        ).execute()
        session = self._create_session(row["diagnosis_code_id"], None)
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
        }

    def revoke(self, session: DemoSession) -> None:
        self.client.table("access_sessions").update({"revoked_at": iso(utc_now())}).eq(
            "id", session.id
        ).execute()

    def diagnosis(self, session: DemoSession, diagnosis_id: str) -> dict:
        response = (
            self.client.table("skin_diagnoses")
            .select("id,skin_type_code,diagnosed_at,disclaimer")
            .eq("id", diagnosis_id)
            .eq("diagnosis_code_id", session.diagnosis_code_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "DIAGNOSIS_NOT_FOUND", "피부 진단 결과를 찾을 수 없습니다.")
        diagnosis = response.data[0]
        skin_type_response = (
            self.client.table("skin_types")
            .select("code,name,summary")
            .eq("code", diagnosis["skin_type_code"])
            .limit(1)
            .execute()
        )
        axes = (
            self.client.table("diagnosis_axes")
            .select("axis_code,selected_value,score")
            .eq("diagnosis_id", diagnosis_id)
            .order("axis_code")
            .execute()
            .data
        )
        metrics = (
            self.client.table("diagnosis_metrics")
            .select("metric_code,metric_name,score,reference_score,level")
            .eq("diagnosis_id", diagnosis_id)
            .order("display_order")
            .execute()
            .data
        )
        return {
            "id": diagnosis["id"],
            "diagnosis_code": diagnosis["skin_type_code"],
            "diagnosed_at": diagnosis["diagnosed_at"],
            "skin_type": skin_type_response.data[0],
            "axes": [
                {"code": row["axis_code"], "selected": row["selected_value"], "score": row["score"]}
                for row in axes
            ],
            "metrics": [
                {
                    "code": row["metric_code"],
                    "name": row["metric_name"],
                    "score": row["score"],
                    "reference_score": row["reference_score"],
                    "level": row["level"],
                }
                for row in metrics
            ],
            "disclaimer": diagnosis["disclaimer"],
        }

    def overview(self, session: DemoSession) -> dict:
        diagnoses = (
            self.client.table("skin_diagnoses")
            .select("id,skin_type_code,diagnosed_at")
            .eq("diagnosis_code_id", session.diagnosis_code_id)
            .order("diagnosed_at", desc=True)
            .limit(1)
            .execute()
            .data
        )
        routines = self._routine_rows(session)
        active = next(
            (self._routine_summary(row) for row in routines if row["status"] != "COMPLETED"),
            None,
        )
        return {
            "user": {"id": session.diagnosis_code_id, "display_name": "사용자"},
            "latest_diagnosis": (
                {
                    "id": diagnoses[0]["id"],
                    "diagnosis_code": diagnoses[0]["skin_type_code"],
                    "diagnosed_at": diagnoses[0]["diagnosed_at"],
                }
                if diagnoses
                else None
            ),
            "active_routine": active,
            "completed_routine_count": sum(row["status"] == "COMPLETED" for row in routines),
        }

    def get_categories(self) -> list[dict]:
        return (
            self.client.table("product_categories")
            .select("code,name,icon_key,default_order,is_required,is_selectable")
            .eq("is_selectable", True)
            .order("default_order")
            .execute()
            .data
        )

    def create_routine(
        self,
        session: DemoSession,
        diagnosis_id: str,
        category_codes: list[str],
    ) -> dict:
        diagnosis = (
            self.client.table("skin_diagnoses")
            .select("id")
            .eq("id", diagnosis_id)
            .eq("diagnosis_code_id", session.diagnosis_code_id)
            .limit(1)
            .execute()
        )
        if not diagnosis.data:
            raise ApiError(404, "DIAGNOSIS_NOT_FOUND", "피부 진단 결과를 찾을 수 없습니다.")
        categories = (
            self.client.table("product_categories")
            .select("id,code")
            .in_("code", list(dict.fromkeys(category_codes)))
            .eq("is_selectable", True)
            .execute()
            .data
        )
        if len(categories) != len(set(category_codes)):
            raise ApiError(422, "INVALID_CATEGORY", "지원하지 않는 카테고리가 포함되어 있습니다.")
        routine = (
            self.client.table("routine_sessions")
            .insert(
                {
                    "diagnosis_code_id": session.diagnosis_code_id,
                    "diagnosis_id": diagnosis_id,
                    "status": "DRAFT",
                }
            )
            .execute()
            .data[0]
        )
        self.client.table("routine_categories").insert(
            [{"routine_id": routine["id"], "category_id": row["id"]} for row in categories]
        ).execute()
        self.record_event(session, "inspection_started", {"routine_id": routine["id"]})
        return self.get_routine(session, routine["id"])

    def list_routines(self, session: DemoSession, status: str | None) -> list[dict]:
        rows = self._routine_rows(session, status)
        return [self._routine_summary(row) for row in rows]

    def _routine_rows(self, session: DemoSession, status: str | None = None) -> list[dict]:
        query = (
            self.client.table("routine_sessions")
            .select("id,diagnosis_id,status,overall_score,created_at,completed_at")
            .eq("diagnosis_code_id", session.diagnosis_code_id)
        )
        if status:
            query = query.eq("status", status)
        return query.order("created_at", desc=True).execute().data

    @staticmethod
    def _routine_summary(row: dict) -> dict:
        return {
            "id": row["id"],
            "status": row["status"],
            "diagnosis_id": row["diagnosis_id"],
            "overall_score": row.get("overall_score"),
            "product_count": row.get("product_count", 0),
            "created_at": row["created_at"],
            "completed_at": row.get("completed_at"),
        }

    def get_routine(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        category_links = (
            self.client.table("routine_categories")
            .select("category_id")
            .eq("routine_id", routine_id)
            .execute()
            .data
        )
        category_ids = [row["category_id"] for row in category_links]
        categories = self._rows_by_ids("product_categories", category_ids, "id,code")
        category_code_by_id = {row["id"]: row["code"] for row in categories}
        product_inputs = self._product_inputs(routine_id, category_code_by_id)
        items = self._routine_items(routine_id)
        return {
            **self._routine_summary({**routine, "product_count": len(items)}),
            "selected_category_codes": [category_code_by_id[row_id] for row_id in category_ids],
            "product_inputs": product_inputs,
            "items": items,
            "updated_at": routine["updated_at"],
        }

    def add_product_input(
        self,
        session: DemoSession,
        routine_id: str,
        input_id: str,
        category_code: str,
        client_product_id: str | None,
        images: list[dict],
    ) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DRAFT"})
        category = (
            self.client.table("product_categories")
            .select("id,code")
            .eq("code", category_code)
            .limit(1)
            .execute()
        )
        if not category.data:
            raise ApiError(422, "INVALID_CATEGORY", "지원하지 않는 카테고리입니다.")
        selected = (
            self.client.table("routine_categories")
            .select("routine_id")
            .eq("routine_id", routine_id)
            .eq("category_id", category.data[0]["id"])
            .limit(1)
            .execute()
        )
        if not selected.data:
            raise ApiError(422, "CATEGORY_NOT_SELECTED", "선택하지 않은 카테고리입니다.")
        scan = (
            self.client.table("product_scans")
            .insert(
                {
                    "id": input_id,
                    "routine_id": routine_id,
                    "category_id": category.data[0]["id"],
                    "client_product_id": client_product_id,
                    "status": "UPLOADED",
                }
            )
            .execute()
            .data[0]
        )
        self.client.table("product_scan_images").insert(
            [
                {
                    "product_scan_id": input_id,
                    "position": index,
                    "image_role": "FRONT" if index == 1 else "OTHER",
                    "original_bucket": image["bucket"],
                    "original_path": image["object_path"],
                    "mime_type": image["mime_type"],
                    "size_bytes": image["size_bytes"],
                    "exif_removed": False,
                }
                for index, image in enumerate(images, start=1)
            ]
        ).execute()
        return {
            "id": scan["id"],
            "category_code": category_code,
            "client_product_id": scan["client_product_id"],
            "status": scan["status"],
            "identified_product": None,
            "images": images,
            "created_at": scan["created_at"],
        }

    def delete_product_input(self, session: DemoSession, routine_id: str, input_id: str) -> None:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DRAFT"})
        response = (
            self.client.table("product_scans")
            .delete()
            .eq("id", input_id)
            .eq("routine_id", routine_id)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "PRODUCT_INPUT_NOT_FOUND", "등록한 제품을 찾을 수 없습니다.")

    def compose(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DRAFT", "COMPOSE_FAILED"})
        scans = (
            self.client.table("product_scans")
            .select("id,category_id")
            .eq("routine_id", routine_id)
            .execute()
            .data
        )
        if not scans:
            raise ApiError(400, "PRODUCT_INPUT_REQUIRED", "제품 사진을 한 개 이상 등록해주세요.")

        self._update_routine(routine_id, {"status": "COMPOSING"})
        self.client.table("routine_items").delete().eq("routine_id", routine_id).execute()
        blueprints = DemoStore._demo_routine_items()
        category_codes = list({item["category_code"] for item in blueprints})
        categories = (
            self.client.table("product_categories")
            .select("id,code")
            .in_("code", category_codes)
            .execute()
            .data
        )
        category_id_by_code = {row["code"]: row["id"] for row in categories}
        inserted_items = []
        for blueprint in blueprints:
            category_id = category_id_by_code[blueprint["category_code"]]
            product_id = self._ensure_product(blueprint["product"], category_id)
            inserted_items.append(
                {
                    "id": blueprint["id"],
                    "routine_id": routine_id,
                    "product_id": product_id,
                    "category_id": category_id,
                    "position": blueprint["position"],
                    "source": "USER_PRODUCT",
                    "item_status": "ACTIVE",
                }
            )
        self.client.table("routine_items").insert(inserted_items).execute()

        for scan in scans:
            match = next(
                (item for item in inserted_items if item["category_id"] == scan["category_id"]),
                inserted_items[0],
            )
            product = self._product(match["product_id"])
            self.client.table("product_scans").update(
                {
                    "matched_product_id": product["id"],
                    "status": "IDENTIFIED",
                    "detected_brand": product["brand"],
                    "detected_name": product["name"],
                    "identification_confidence": 0.95,
                    "ai_metadata": {"mode": "deterministic-demo", "prompt_pending": True},
                }
            ).eq("id", scan["id"]).execute()

        job = self._complete_job("ROUTINE_COMPOSITION", routine_id)
        self._update_routine(routine_id, {"status": "REVIEW_REQUIRED"})
        return job

    def reorder(self, session: DemoSession, routine_id: str, requested: list[dict]) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"REVIEW_REQUIRED"})
        rows = (
            self.client.table("routine_items")
            .select("id,position")
            .eq("routine_id", routine_id)
            .eq("item_status", "ACTIVE")
            .execute()
            .data
        )
        existing_ids = {row["id"] for row in rows}
        requested_ids = {row["routine_item_id"] for row in requested}
        positions = [row["position"] for row in requested]
        if (
            requested_ids != existing_ids
            or len(requested_ids) != len(requested)
            or len(positions) != len(set(positions))
        ):
            raise ApiError(422, "INVALID_ROUTINE_ORDER", "전체 루틴 항목을 중복 없이 보내주세요.")
        for index, row in enumerate(rows, start=1):
            self.client.table("routine_items").update({"position": 10000 + index}).eq(
                "id", row["id"]
            ).execute()
        for row in requested:
            self.client.table("routine_items").update({"position": row["position"]}).eq(
                "id", row["routine_item_id"]
            ).execute()
        return self.get_routine(session, routine_id)

    def confirm(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"REVIEW_REQUIRED"})
        self._update_routine(
            routine_id,
            {"status": "CONFIRMED", "confirmed_at": iso(utc_now())},
        )
        self.record_event(session, "routine_review_completed", {"routine_id": routine_id})
        return self.get_routine(session, routine_id)

    def analyze(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"CONFIRMED", "ANALYSIS_FAILED"})
        self._update_routine(routine_id, {"status": "ANALYZING"})
        items = (
            self.client.table("routine_items")
            .select("id,product_id")
            .eq("routine_id", routine_id)
            .eq("item_status", "ACTIVE")
            .execute()
            .data
        )
        products = self._rows_by_ids(
            "products",
            [row["product_id"] for row in items],
            "id,brand,name",
        )
        product_by_id = {row["id"]: row for row in products}
        item_ids = [row["id"] for row in items]
        if item_ids:
            self.client.table("product_analyses").delete().in_(
                "routine_item_id", item_ids
            ).execute()

        aac = (
            self.client.table("products")
            .select("id,brand,name,price_amount,image_bucket,image_path")
            .eq("is_aac", True)
            .eq("is_verified", True)
            .order("created_at")
            .limit(1)
            .execute()
        )
        if not aac.data:
            raise ApiError(503, "AAC_PRODUCT_UNAVAILABLE", "AAC 대체 제품 데이터가 없습니다.")
        aac_product = aac.data[0]
        for item in items:
            product = product_by_id[item["product_id"]]
            if "BHA 2%" in product["name"]:
                score, verdict = 22, "REMOVE"
                reasons = ["민감 피부에 자극 가능성이 있는 성분이 포함되어 있습니다."]
                flagged = [{"name": "에탄올", "reason": "민감도 악화 가능", "severity": "HIGH"}]
            elif "MISSHA" in product["brand"]:
                score, verdict = 22, "CHOICE"
                reasons = [
                    "현재 피부 상태에서는 여러 활성 성분을 함께 사용하는 빈도를 조절해주세요."
                ]
                flagged = [{"name": "향료", "reason": "자극 가능", "severity": "MEDIUM"}]
            else:
                score, verdict = 82, "KEEP"
                reasons = ["현재 피부 상태와 루틴 단계에 적합한 제품입니다."]
                flagged = []
            analysis_id = str(uuid4())
            self.client.table("product_analyses").insert(
                {
                    "id": analysis_id,
                    "routine_item_id": item["id"],
                    "score": score,
                    "verdict": verdict,
                    "reasons": reasons,
                    "flagged_ingredients": flagged,
                    "model_version": "prompt-pending",
                    "analysis_version": "demo-v1",
                }
            ).execute()
            if verdict == "REMOVE":
                self.client.table("replacement_recommendations").insert(
                    {
                        "product_analysis_id": analysis_id,
                        "replacement_product_id": aac_product["id"],
                        "replacement_score": 91,
                        "required_single_step": True,
                        "reasons": ["민감 피부를 고려한 AAC 대체 제품입니다."],
                        "comparison": {
                            "improved_ingredients": ["판테놀", "병풀추출물"],
                            "excluded_ingredients": ["에탄올", "향료"],
                        },
                    }
                ).execute()
        job = self._complete_job("SUITABILITY_ANALYSIS", routine_id)
        self._update_routine(routine_id, {"status": "DECISION_REQUIRED", "overall_score": 68})
        return job

    def get_analysis(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        items = self._routine_items(routine_id, include_inactive=True)
        item_by_id = {item["id"]: item for item in items}
        analyses = (
            self.client.table("product_analyses")
            .select(
                "id,routine_item_id,score,verdict,reasons,flagged_ingredients,model_version,analysis_version"
            )
            .in_("routine_item_id", list(item_by_id))
            .execute()
            .data
            if item_by_id
            else []
        )
        if not analyses:
            raise ApiError(404, "ANALYSIS_NOT_FOUND", "적합도 분석 결과가 아직 없습니다.")
        analysis_ids = [row["id"] for row in analyses]
        recommendations = (
            self.client.table("replacement_recommendations")
            .select(
                "id,product_analysis_id,replacement_product_id,replacement_score,"
                "required_single_step,comparison,decision"
            )
            .in_("product_analysis_id", analysis_ids)
            .execute()
            .data
        )
        replacement_products = self._rows_by_ids(
            "products",
            [row["replacement_product_id"] for row in recommendations],
            "id,brand,name,price_amount,image_bucket,image_path",
        )
        product_by_id = {row["id"]: row for row in replacement_products}
        recommendation_by_analysis = {row["product_analysis_id"]: row for row in recommendations}
        output_items = []
        for analysis in analyses:
            recommendation_row = recommendation_by_analysis.get(analysis["id"])
            recommendation = None
            if recommendation_row:
                product = product_by_id[recommendation_row["replacement_product_id"]]
                recommendation = {
                    "id": recommendation_row["id"],
                    "required_single_step": recommendation_row["required_single_step"],
                    "decision": recommendation_row["decision"],
                    "replacement_product": {
                        "id": product["id"],
                        "brand": product["brand"],
                        "name": product["name"],
                        "score": recommendation_row["replacement_score"],
                        "price": product["price_amount"],
                        "image_url": self._product_image_url(product),
                    },
                    "comparison": recommendation_row["comparison"],
                }
            output_items.append(
                {
                    "routine_item_id": analysis["routine_item_id"],
                    "score": analysis["score"],
                    "verdict": analysis["verdict"],
                    "reasons": analysis["reasons"],
                    "flagged_ingredients": analysis["flagged_ingredients"],
                    "recommendation": recommendation,
                }
            )
        self.record_event(session, "analysis_viewed", {"routine_id": routine_id})
        return {
            "routine_id": routine_id,
            "overall_score": routine["overall_score"],
            "summary": {
                "total": len(output_items),
                "unsuitable": sum(row["verdict"] != "KEEP" for row in output_items),
            },
            "items": output_items,
            "analysis_version": analyses[0]["analysis_version"],
            "model_version": analyses[0]["model_version"],
            "disclaimer": DISCLAIMER,
        }

    def decide(
        self,
        session: DemoSession,
        routine_id: str,
        recommendation_id: str,
        decision: str,
    ) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DECISION_REQUIRED"})
        recommendation_response = (
            self.client.table("replacement_recommendations")
            .select("id,product_analysis_id,replacement_product_id,decision")
            .eq("id", recommendation_id)
            .limit(1)
            .execute()
        )
        if not recommendation_response.data:
            raise ApiError(404, "RECOMMENDATION_NOT_FOUND", "교체 추천을 찾을 수 없습니다.")
        recommendation = recommendation_response.data[0]
        if recommendation["decision"] is not None:
            raise ApiError(409, "RECOMMENDATION_ALREADY_DECIDED", "이미 처리한 추천입니다.")
        analysis = (
            self.client.table("product_analyses")
            .select("routine_item_id")
            .eq("id", recommendation["product_analysis_id"])
            .limit(1)
            .execute()
            .data[0]
        )
        item = (
            self.client.table("routine_items")
            .select("id,routine_id,category_id,position")
            .eq("id", analysis["routine_item_id"])
            .eq("routine_id", routine_id)
            .limit(1)
            .execute()
        )
        if not item.data:
            raise ApiError(404, "RECOMMENDATION_NOT_FOUND", "루틴의 교체 추천이 아닙니다.")
        original = item.data[0]
        self.client.table("replacement_recommendations").update(
            {"decision": decision, "decided_at": iso(utc_now())}
        ).eq("id", recommendation_id).execute()

        if decision == "REPLACE":
            temporary_position = 20000 + int(original["position"])
            self.client.table("routine_items").update(
                {"position": temporary_position, "item_status": "REPLACED"}
            ).eq("id", original["id"]).execute()
            self.client.table("routine_items").insert(
                {
                    "routine_id": routine_id,
                    "product_id": recommendation["replacement_product_id"],
                    "category_id": original["category_id"],
                    "position": original["position"],
                    "source": "AAC_REPLACEMENT",
                    "item_status": "ACTIVE",
                    "replaced_item_id": original["id"],
                }
            ).execute()
            product = self._product(recommendation["replacement_product_id"])
            self._add_cart_item(
                session,
                routine_id,
                recommendation_id,
                product,
            )
            self.record_event(
                session,
                "replacement_added",
                {"routine_id": routine_id, "recommendation_id": recommendation_id},
            )
        else:
            self.client.table("routine_items").update({"item_status": "REMOVED"}).eq(
                "id", original["id"]
            ).execute()

        remaining = (
            self.client.table("replacement_recommendations")
            .select("id,product_analyses!inner(routine_items!inner(routine_id))")
            .is_("decision", "null")
            .eq("product_analyses.routine_items.routine_id", routine_id)
            .execute()
            .data
        )
        if not remaining:
            self._update_routine(
                routine_id,
                {"status": "COMPLETED", "completed_at": iso(utc_now())},
            )
        return self.final_routine(session, routine_id)

    def final_routine(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        items = self._routine_items(routine_id)
        items.sort(key=lambda row: row["position"])
        for position, item in enumerate(items, start=1):
            item["position"] = position
        cart = self.cart(session)
        return {
            "routine_id": routine_id,
            "status": routine["status"],
            "items": items,
            "cart_item_count": len(cart["items"]),
            "completed_at": routine["completed_at"],
        }

    def cart(self, session: DemoSession) -> dict:
        cart = self._active_cart(session, create=False)
        if cart is None:
            return {
                "items": [],
                "subtotal_amount": 0,
                "total_amount": 0,
                "currency": "KRW",
            }
        rows = (
            self.client.table("cart_items")
            .select("id,product_id,recommendation_id,quantity,unit_price")
            .eq("cart_id", cart["id"])
            .order("created_at")
            .execute()
            .data
        )
        products = self._rows_by_ids(
            "products",
            [row["product_id"] for row in rows],
            "id,brand,name,image_bucket,image_path",
        )
        product_by_id = {row["id"]: row for row in products}
        items = []
        for row in rows:
            product = product_by_id[row["product_id"]]
            items.append(
                {
                    "id": row["id"],
                    "routine_id": cart["routine_id"],
                    "recommendation_id": row["recommendation_id"],
                    "product": {
                        "id": product["id"],
                        "brand": product["brand"],
                        "name": product["name"],
                        "image_url": self._product_image_url(product),
                    },
                    "unit_price": row["unit_price"],
                    "quantity": row["quantity"],
                    "line_total": row["unit_price"] * row["quantity"],
                }
            )
        total = sum(row["line_total"] for row in items)
        if total != cart["total_amount"]:
            self.client.table("carts").update({"total_amount": total}).eq(
                "id", cart["id"]
            ).execute()
        return {
            "items": items,
            "subtotal_amount": total,
            "total_amount": total,
            "currency": cart["currency"],
        }

    def update_cart_item(self, session: DemoSession, item_id: str, quantity: int) -> dict:
        cart, item = self._require_cart_item(session, item_id)
        self.client.table("cart_items").update({"quantity": quantity}).eq(
            "id", item["id"]
        ).execute()
        self._refresh_cart_total(cart["id"])
        return self.cart(session)

    def delete_cart_item(self, session: DemoSession, item_id: str) -> None:
        cart, item = self._require_cart_item(session, item_id)
        self.client.table("cart_items").delete().eq("id", item["id"]).execute()
        self._refresh_cart_total(cart["id"])

    def create_order(self, session: DemoSession, payment_method: str, return_url: str) -> dict:
        cart = self._active_cart(session, create=False)
        cart_data = self.cart(session)
        if cart is None or not cart_data["items"]:
            raise ApiError(400, "CART_EMPTY", "장바구니가 비어 있습니다.")
        order = (
            self.client.table("orders")
            .insert(
                {
                    "diagnosis_code_id": session.diagnosis_code_id,
                    "routine_id": cart["routine_id"],
                    "cart_id": cart["id"],
                    "order_number": f"WL-{utc_now():%Y%m%d}-{uuid4().hex[:8].upper()}",
                    "status": "PENDING_PAYMENT",
                    "payment_provider": "MOCK",
                    "payment_method": payment_method,
                    "subtotal_amount": cart_data["subtotal_amount"],
                    "total_amount": cart_data["total_amount"],
                    "currency": "KRW",
                }
            )
            .execute()
            .data[0]
        )
        self.client.table("order_items").insert(
            [
                {
                    "order_id": order["id"],
                    "product_id": item["product"]["id"],
                    "brand_snapshot": item["product"]["brand"],
                    "name_snapshot": item["product"]["name"],
                    "unit_price": item["unit_price"],
                    "quantity": item["quantity"],
                }
                for item in cart_data["items"]
            ]
        ).execute()
        self.record_event(session, "checkout_started", {"order_id": order["id"]})
        return self._public_order(order, return_url)

    def get_order(self, session: DemoSession, order_id: str) -> dict:
        response = (
            self.client.table("orders")
            .select("*")
            .eq("id", order_id)
            .eq("diagnosis_code_id", session.diagnosis_code_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
        order = response.data[0]
        if order["status"] == "PENDING_PAYMENT":
            paid_at = iso(utc_now())
            order = (
                self.client.table("orders")
                .update({"status": "PAID", "paid_at": paid_at})
                .eq("id", order_id)
                .execute()
                .data[0]
            )
            if order["cart_id"]:
                self.client.table("carts").update({"status": "CONVERTED"}).eq(
                    "id", order["cart_id"]
                ).execute()
            self.record_event(session, "payment_completed", {"order_id": order_id})
        return self._public_order(order, None)

    def get_job(self, session: DemoSession, job_id: str) -> dict:
        response = (
            self.client.table("ai_analysis_runs")
            .select(
                "id,job_type,routine_id,status,progress,error_code,error_message,queued_at,completed_at"
            )
            .eq("id", job_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "JOB_NOT_FOUND", "분석 작업을 찾을 수 없습니다.")
        row = response.data[0]
        self._require_routine(session, row["routine_id"])
        return {
            "id": row["id"],
            "type": row["job_type"],
            "routine_id": row["routine_id"],
            "status": row["status"],
            "progress": row["progress"],
            "error": (
                {"code": row["error_code"], "message": row["error_message"]}
                if row["error_code"]
                else None
            ),
            "created_at": row["queued_at"],
            "completed_at": row["completed_at"],
        }

    def record_event(
        self,
        session: DemoSession,
        name: str,
        properties: dict,
        occurred_at: str | None = None,
    ) -> None:
        if name not in self.allowed_events:
            raise ApiError(422, "INVALID_EVENT_NAME", f"허용되지 않은 이벤트입니다: {name}")
        self.client.table("analytics_events").insert(
            {
                "diagnosis_code_id": session.diagnosis_code_id,
                "access_session_id": session.id,
                "routine_id": properties.get("routine_id"),
                "event_name": name,
                "occurred_at": occurred_at or iso(utc_now()),
                "properties": properties,
            }
        ).execute()

    def _require_routine(self, session: DemoSession, routine_id: str) -> dict:
        response = (
            self.client.table("routine_sessions")
            .select("*")
            .eq("id", routine_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "ROUTINE_NOT_FOUND", "루틴을 찾을 수 없습니다.")
        routine = response.data[0]
        if routine["diagnosis_code_id"] != session.diagnosis_code_id:
            raise ApiError(403, "ROUTINE_FORBIDDEN", "다른 사용자의 루틴에는 접근할 수 없습니다.")
        return routine

    @staticmethod
    def _require_state(routine: dict, allowed: set[str]) -> None:
        if routine["status"] not in allowed:
            raise ApiError(
                409, "ROUTINE_STATE_CONFLICT", "현재 루틴 상태에서는 실행할 수 없습니다."
            )

    def _update_routine(self, routine_id: str, values: dict) -> None:
        self.client.table("routine_sessions").update(values).eq("id", routine_id).execute()

    def _rows_by_ids(self, table: str, ids: list[str], columns: str) -> list[dict]:
        unique_ids = list(dict.fromkeys(ids))
        if not unique_ids:
            return []
        return self.client.table(table).select(columns).in_("id", unique_ids).execute().data

    def _product_inputs(self, routine_id: str, category_code_by_id: dict[str, str]) -> list[dict]:
        scans = (
            self.client.table("product_scans")
            .select("id,category_id,client_product_id,status,matched_product_id,created_at")
            .eq("routine_id", routine_id)
            .order("created_at")
            .execute()
            .data
        )
        scan_ids = [row["id"] for row in scans]
        images = (
            self.client.table("product_scan_images")
            .select("product_scan_id,original_bucket,original_path,mime_type,size_bytes,position")
            .in_("product_scan_id", scan_ids)
            .order("position")
            .execute()
            .data
            if scan_ids
            else []
        )
        images_by_scan: dict[str, list[dict]] = {}
        for image in images:
            images_by_scan.setdefault(image["product_scan_id"], []).append(
                {
                    "bucket": image["original_bucket"],
                    "object_path": image["original_path"],
                    "mime_type": image["mime_type"],
                    "size_bytes": image["size_bytes"],
                }
            )
        products = self._rows_by_ids(
            "products",
            [row["matched_product_id"] for row in scans if row["matched_product_id"]],
            "id,brand,name,image_bucket,image_path",
        )
        product_by_id = {row["id"]: row for row in products}
        output = []
        for scan in scans:
            product = product_by_id.get(scan["matched_product_id"])
            output.append(
                {
                    "id": scan["id"],
                    "category_code": category_code_by_id.get(scan["category_id"]),
                    "client_product_id": scan["client_product_id"],
                    "status": scan["status"],
                    "identified_product": (
                        {
                            "id": product["id"],
                            "brand": product["brand"],
                            "name": product["name"],
                            "image_url": self._product_image_url(product),
                        }
                        if product
                        else None
                    ),
                    "images": images_by_scan.get(scan["id"], []),
                    "created_at": scan["created_at"],
                }
            )
        return output

    def _routine_items(self, routine_id: str, *, include_inactive: bool = False) -> list[dict]:
        query = (
            self.client.table("routine_items")
            .select("id,product_id,category_id,position,source,item_status,replaced_item_id")
            .eq("routine_id", routine_id)
        )
        if not include_inactive:
            query = query.eq("item_status", "ACTIVE")
        rows = query.order("position").execute().data
        products = self._rows_by_ids(
            "products",
            [row["product_id"] for row in rows],
            "id,brand,name,image_bucket,image_path",
        )
        categories = self._rows_by_ids(
            "product_categories",
            [row["category_id"] for row in rows],
            "id,code,name",
        )
        product_by_id = {row["id"]: row for row in products}
        category_by_id = {row["id"]: row for row in categories}
        output = []
        for row in rows:
            product = product_by_id[row["product_id"]]
            category = category_by_id[row["category_id"]]
            output.append(
                {
                    "id": row["id"],
                    "position": row["position"],
                    "category_code": category["code"],
                    "product": {
                        "id": product["id"],
                        "brand": product["brand"],
                        "name": product["name"],
                        "category_name": category["name"],
                        "image_url": self._product_image_url(product),
                    },
                    "source": (
                        "AAC_REPLACEMENT" if row["source"] == "AAC_REPLACEMENT" else "AI_COMPOSED"
                    ),
                    "is_removed": row["item_status"] == "REMOVED",
                    "is_replacement": row["source"] == "AAC_REPLACEMENT",
                    "purchased": False,
                }
            )
        return output

    def _ensure_product(self, product: dict, category_id: str) -> str:
        response = (
            self.client.table("products")
            .select("id")
            .eq("brand", product["brand"])
            .eq("name", product["name"])
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]["id"]
        created = (
            self.client.table("products")
            .insert(
                {
                    "category_id": category_id,
                    "brand": product["brand"],
                    "name": product["name"],
                    "source": "AI_DETECTED",
                    "is_aac": False,
                    "is_verified": False,
                    "metadata": {"mode": "deterministic-demo"},
                }
            )
            .execute()
            .data[0]
        )
        return created["id"]

    def _product(self, product_id: str) -> dict:
        response = (
            self.client.table("products")
            .select("id,brand,name,price_amount,image_bucket,image_path")
            .eq("id", product_id)
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "PRODUCT_NOT_FOUND", "제품을 찾을 수 없습니다.")
        return response.data[0]

    def _product_image_url(self, product: dict) -> str | None:
        if not product.get("image_bucket") or not product.get("image_path"):
            return None
        return self.client.storage.from_(product["image_bucket"]).get_public_url(
            product["image_path"]
        )

    def _complete_job(self, job_type: str, routine_id: str) -> dict:
        now = iso(utc_now())
        row = (
            self.client.table("ai_analysis_runs")
            .insert(
                {
                    "routine_id": routine_id,
                    "job_type": job_type,
                    "status": "SUCCEEDED",
                    "progress": 100,
                    "provider": "OPENAI",
                    "model_name": "prompt-pending",
                    "prompt_version": "pending",
                    "analysis_version": "demo-v1",
                    "input_payload": {"mode": "deterministic-demo"},
                    "output_payload": {"normalized": True},
                    "started_at": now,
                    "completed_at": now,
                }
            )
            .execute()
            .data[0]
        )
        return {
            "id": row["id"],
            "type": row["job_type"],
            "routine_id": routine_id,
            "status": row["status"],
            "progress": row["progress"],
            "error": None,
            "created_at": row["queued_at"],
            "completed_at": row["completed_at"],
        }

    def _active_cart(self, session: DemoSession, *, create: bool) -> dict | None:
        response = (
            self.client.table("carts")
            .select("id,routine_id,total_amount,currency,status")
            .eq("diagnosis_code_id", session.diagnosis_code_id)
            .eq("status", "ACTIVE")
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]
        if not create:
            return None
        return (
            self.client.table("carts")
            .insert(
                {
                    "diagnosis_code_id": session.diagnosis_code_id,
                    "status": "ACTIVE",
                    "total_amount": 0,
                    "currency": "KRW",
                }
            )
            .execute()
            .data[0]
        )

    def _add_cart_item(
        self,
        session: DemoSession,
        routine_id: str,
        recommendation_id: str,
        product: dict,
    ) -> None:
        cart = self._active_cart(session, create=True)
        if cart["routine_id"] != routine_id:
            self.client.table("carts").update({"routine_id": routine_id}).eq(
                "id", cart["id"]
            ).execute()
        existing = (
            self.client.table("cart_items")
            .select("id")
            .eq("cart_id", cart["id"])
            .eq("product_id", product["id"])
            .limit(1)
            .execute()
        )
        if not existing.data:
            self.client.table("cart_items").insert(
                {
                    "cart_id": cart["id"],
                    "product_id": product["id"],
                    "recommendation_id": recommendation_id,
                    "quantity": 1,
                    "unit_price": product["price_amount"] or 0,
                }
            ).execute()
        self._refresh_cart_total(cart["id"])

    def _refresh_cart_total(self, cart_id: str) -> None:
        rows = (
            self.client.table("cart_items")
            .select("unit_price,quantity")
            .eq("cart_id", cart_id)
            .execute()
            .data
        )
        total = sum(row["unit_price"] * row["quantity"] for row in rows)
        self.client.table("carts").update({"total_amount": total}).eq("id", cart_id).execute()

    def _require_cart_item(self, session: DemoSession, item_id: str) -> tuple[dict, dict]:
        cart = self._active_cart(session, create=False)
        if cart is None:
            raise ApiError(404, "CART_ITEM_NOT_FOUND", "장바구니 상품을 찾을 수 없습니다.")
        response = (
            self.client.table("cart_items")
            .select("id")
            .eq("id", item_id)
            .eq("cart_id", cart["id"])
            .limit(1)
            .execute()
        )
        if not response.data:
            raise ApiError(404, "CART_ITEM_NOT_FOUND", "장바구니 상품을 찾을 수 없습니다.")
        return cart, response.data[0]

    @staticmethod
    def _public_order(order: dict, return_url: str | None) -> dict:
        return {
            "id": order["id"],
            "order_number": order["order_number"],
            "status": order["status"],
            "total_amount": order["total_amount"],
            "currency": order["currency"],
            "payment_method": order["payment_method"],
            "payment_action": (
                {
                    "type": "DEEPLINK",
                    "url": f"{return_url}?mock_order_id={order['id']}",
                }
                if order["status"] == "PENDING_PAYMENT" and return_url
                else None
            ),
            "paid_at": order["paid_at"],
        }


supabase_store = SupabaseStore()
