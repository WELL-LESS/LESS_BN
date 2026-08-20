from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.errors import ApiError

DEMO_CODE = "WHS-2026-1234"
DEMO_CODE_ID = "10000000-0000-0000-0000-000000000001"
DEMO_DIAGNOSIS_ID = "20000000-0000-0000-0000-000000000001"
AAC_PRODUCT_ID = "30000000-0000-0000-0000-000000000001"
DISCLAIMER = "성분 및 피부 정보에 기반한 참고 결과이며 의료적 진단이 아닙니다."


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


@dataclass
class DemoSession:
    id: str
    diagnosis_code_id: str
    access_token: str
    refresh_token: str
    expires_at: datetime
    refresh_expires_at: datetime
    revoked_at: datetime | None = None


class DemoStore:
    """Process-local MVP store matching API v1 while external integrations are unavailable."""

    allowed_events = {
        "code_verified",
        "inspection_started",
        "routine_review_completed",
        "analysis_viewed",
        "replacement_viewed",
        "replacement_added",
        "cart_viewed",
        "checkout_started",
        "payment_completed",
    }

    def __init__(self) -> None:
        self._code_hash = hashlib.sha256(DEMO_CODE.encode()).hexdigest()
        self.sessions: dict[str, DemoSession] = {}
        self.refresh_sessions: dict[str, DemoSession] = {}
        self.routines: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.cart_items: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.events: list[dict] = []

        self.categories = [
            self._category("CLEANSING_FOAM_GEL", "클렌징폼/젤", "cleansing_foam", 10, True),
            self._category("CLEANSING_OIL_BALM", "클렌징오일/밤", "cleansing_oil", 20),
            self._category("EXFOLIATOR", "필링&스크럽", "exfoliator", 30),
            self._category("CLEANSING_WATER_MILK", "클렌징워터/밀크", "cleansing_water", 40),
            self._category("SKIN_TONER", "스킨/토너", "toner", 50),
            self._category("ESSENCE_SERUM_AMPOULE", "에센스/세럼/앰플", "serum", 60),
            self._category("LOTION", "로션", "lotion", 70),
            self._category("MIST_OIL", "미스트/오일", "mist_oil", 80),
        ]

    @staticmethod
    def _category(
        code: str,
        name: str,
        icon_key: str,
        default_order: int,
        is_required: bool = False,
    ) -> dict:
        return {
            "code": code,
            "name": name,
            "icon_key": icon_key,
            "default_order": default_order,
            "is_required": is_required,
            "is_selectable": True,
        }

    def verify_code(self, personal_code: str, _device_id: str) -> dict:
        candidate_hash = hashlib.sha256(personal_code.strip().encode()).hexdigest()
        if not secrets.compare_digest(candidate_hash, self._code_hash):
            raise ApiError(
                401,
                "INVALID_PERSONAL_CODE",
                "개인 코드를 확인해주세요.",
                field="personal_code",
            )
        session = self._create_session()
        self.record_event(session, "code_verified", {})
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
            "user": {"id": DEMO_CODE_ID, "display_name": "사용자"},
            "latest_diagnosis_id": DEMO_DIAGNOSIS_ID,
        }

    def _create_session(self) -> DemoSession:
        session = DemoSession(
            id=str(uuid4()),
            diagnosis_code_id=DEMO_CODE_ID,
            access_token=secrets.token_urlsafe(32),
            refresh_token=secrets.token_urlsafe(40),
            expires_at=utc_now() + timedelta(hours=1),
            refresh_expires_at=utc_now() + timedelta(days=7),
        )
        self.sessions[session.access_token] = session
        self.refresh_sessions[session.refresh_token] = session
        return session

    def get_session(self, access_token: str) -> DemoSession | None:
        session = self.sessions.get(access_token)
        if not session or session.revoked_at or session.expires_at <= utc_now():
            return None
        return session

    def refresh(self, refresh_token: str) -> dict:
        old_session = self.refresh_sessions.get(refresh_token)
        if (
            old_session is None
            or old_session.revoked_at
            or old_session.refresh_expires_at <= utc_now()
        ):
            raise ApiError(401, "REFRESH_TOKEN_EXPIRED", "다시 개인 코드를 입력해주세요.")
        self.revoke(old_session)
        session = self._create_session()
        return {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,
        }

    def revoke(self, session: DemoSession) -> None:
        session.revoked_at = utc_now()

    def diagnosis(self, _session: DemoSession, diagnosis_id: str) -> dict:
        if diagnosis_id != DEMO_DIAGNOSIS_ID:
            raise ApiError(404, "DIAGNOSIS_NOT_FOUND", "피부 진단 결과를 찾을 수 없습니다.")
        return {
            "id": DEMO_DIAGNOSIS_ID,
            "diagnosis_code": "OSP",
            "diagnosed_at": "2026-08-15T09:30:00+09:00",
            "skin_type": {
                "code": "OSP",
                "name": "지성·민감성·색소성",
                "summary": "피지 분비가 많고 외부 자극에 민감하며 색소 고민이 있는 피부",
            },
            "axes": [
                {"code": "O_D", "selected": "O", "score": 72},
                {"code": "S_R", "selected": "S", "score": 66},
                {"code": "P_N", "selected": "P", "score": 61},
            ],
            "metrics": [
                {
                    "code": "PORE",
                    "name": "모공",
                    "score": 79,
                    "reference_score": 44,
                    "level": "CAUTION",
                },
                {
                    "code": "BLACKHEAD",
                    "name": "블랙헤드",
                    "score": 61,
                    "reference_score": 56,
                    "level": "NORMAL",
                },
                {
                    "code": "GLOW",
                    "name": "광채",
                    "score": 86,
                    "reference_score": 77,
                    "level": "GOOD",
                },
                {
                    "code": "REDNESS",
                    "name": "홍조",
                    "score": 91,
                    "reference_score": 75,
                    "level": "HIGH",
                },
                {
                    "code": "DARK_CIRCLE",
                    "name": "다크서클",
                    "score": 89,
                    "reference_score": 98,
                    "level": "CAUTION",
                },
                {
                    "code": "ACNE",
                    "name": "여드름",
                    "score": 86,
                    "reference_score": 89,
                    "level": "CAUTION",
                },
            ],
            "images": [],
            "disclaimer": "본 결과는 의료적 진단이 아닙니다.",
        }

    def skin_type_catalog(self) -> list[dict]:
        return [
            {
                "code": "O",
                "label": "지성",
                "title": "지성 피부",
                "description": "피지 분비가 많고 모공이 넓은 유형",
                "display_order": 10,
                "types": [
                    self._skin_type("OSP", "지성·민감성·색소성"),
                    self._skin_type("OSN", "지성·민감성·비색소성"),
                    self._skin_type("ORP", "지성·저항성·색소성"),
                    self._skin_type("ORN", "지성·저항성·비색소성"),
                ],
            },
            {
                "code": "D",
                "label": "건성",
                "title": "건성 피부",
                "description": "수분과 유분이 부족해 건조함을 느끼는 유형",
                "display_order": 20,
                "types": [
                    self._skin_type("DSP", "건성·민감성·색소성"),
                    self._skin_type("DSN", "건성·민감성·비색소성"),
                    self._skin_type("DRP", "건성·저항성·색소성"),
                    self._skin_type("DRN", "건성·저항성·비색소성"),
                ],
            },
            {
                "code": "C",
                "label": "복합성",
                "title": "복합성 피부",
                "description": "부위에 따라 유분과 건조함이 함께 나타나는 유형",
                "display_order": 30,
                "types": [
                    self._skin_type("CSP", "복합성·민감성·색소성"),
                    self._skin_type("CSN", "복합성·민감성·비색소성"),
                    self._skin_type("CRP", "복합성·저항성·색소성"),
                    self._skin_type("CRN", "복합성·저항성·비색소성"),
                ],
            },
        ]

    @staticmethod
    def _skin_type(code: str, name: str) -> dict:
        return {"code": code, "name": name, "summary": name}

    def overview(self, session: DemoSession) -> dict:
        owned = self._owned_routines(session)
        active = next(
            (
                self._routine_summary(item)
                for item in reversed(owned)
                if item["status"] != "COMPLETED"
            ),
            None,
        )
        completed = [item for item in owned if item["status"] == "COMPLETED"]
        return {
            "user": {"id": DEMO_CODE_ID, "display_name": "사용자"},
            "latest_diagnosis": {
                "id": DEMO_DIAGNOSIS_ID,
                "diagnosis_code": "OSP",
                "diagnosed_at": "2026-08-15T09:30:00+09:00",
            },
            "active_routine": active,
            "completed_routine_count": len(completed),
        }

    def get_categories(self) -> list[dict]:
        return self.categories

    def create_routine(
        self, session: DemoSession, diagnosis_id: str, category_codes: list[str]
    ) -> dict:
        if diagnosis_id != DEMO_DIAGNOSIS_ID:
            raise ApiError(404, "DIAGNOSIS_NOT_FOUND", "피부 진단 결과를 찾을 수 없습니다.")
        valid = {category["code"] for category in self.categories}
        invalid = sorted(set(category_codes) - valid)
        if invalid:
            raise ApiError(
                422, "INVALID_CATEGORY", f"지원하지 않는 카테고리입니다: {', '.join(invalid)}"
            )
        now = utc_now()
        routine_id = str(uuid4())
        routine = {
            "id": routine_id,
            "diagnosis_code_id": session.diagnosis_code_id,
            "diagnosis_id": diagnosis_id,
            "status": "DRAFT",
            "selected_category_codes": list(dict.fromkeys(category_codes)),
            "product_inputs": [],
            "items": [],
            "analysis": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        self.routines[routine_id] = routine
        self.record_event(session, "inspection_started", {"routine_id": routine_id})
        return self._routine_detail(routine)

    def list_routines(self, session: DemoSession, status: str | None) -> list[dict]:
        routines = self._owned_routines(session)
        if status:
            routines = [routine for routine in routines if routine["status"] == status]
        return [self._routine_summary(routine) for routine in reversed(routines)]

    def get_routine(self, session: DemoSession, routine_id: str) -> dict:
        return self._routine_detail(self._require_routine(session, routine_id))

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
        if category_code not in routine["selected_category_codes"]:
            raise ApiError(422, "CATEGORY_NOT_SELECTED", "선택하지 않은 카테고리입니다.")
        product_input = {
            "id": input_id,
            "category_code": category_code,
            "client_product_id": client_product_id,
            "status": "UPLOADED",
            "identified_product": None,
            "images": images,
            "created_at": iso(utc_now()),
        }
        routine["product_inputs"].append(product_input)
        routine["updated_at"] = utc_now()
        return product_input

    def delete_product_input(self, session: DemoSession, routine_id: str, input_id: str) -> None:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DRAFT"})
        original_count = len(routine["product_inputs"])
        routine["product_inputs"] = [
            item for item in routine["product_inputs"] if item["id"] != input_id
        ]
        if len(routine["product_inputs"]) == original_count:
            raise ApiError(404, "PRODUCT_INPUT_NOT_FOUND", "등록한 제품을 찾을 수 없습니다.")

    def compose(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DRAFT", "COMPOSE_FAILED"})
        if not routine["product_inputs"]:
            raise ApiError(400, "PRODUCT_INPUT_REQUIRED", "제품 사진을 한 개 이상 등록해주세요.")
        routine["status"] = "COMPOSING"
        routine["items"] = self._demo_routine_items()
        for product_input in routine["product_inputs"]:
            product_input["status"] = "IDENTIFIED"
            product_input["identified_product"] = routine["items"][0]["product"]
        routine["status"] = "REVIEW_REQUIRED"
        routine["updated_at"] = utc_now()
        return self._complete_job("COMPOSE", routine_id)

    @staticmethod
    def _demo_routine_items() -> list[dict]:
        products = [
            ("COSRX", "오일-프리 울트라 모이스처라이징 클렌저", "클렌저", "CLEANSING_FOAM_GEL"),
            ("Klairs", "서플 프레퍼레이션 언센티드 토너", "토너", "SKIN_TONER"),
            ("COSRX", "AHA/BHA 클라리파잉 트리트먼트 토너", "토너", "SKIN_TONER"),
            ("The Ordinary", "나이아신아마이드 10% + 징크 1%", "세럼", "ESSENCE_SERUM_AMPOULE"),
            ("Paula's Choice", "BHA 2% 리퀴드 엑스폴리언트", "세럼", "ESSENCE_SERUM_AMPOULE"),
            ("MISSHA", "타임 레볼루션 나이트 리페어 앰플", "앰플", "ESSENCE_SERUM_AMPOULE"),
            ("Laneige", "워터뱅크 블루 히알루론산 크림", "크림", "CREAM"),
            ("Anessa", "퍼펙트 UV 선스크린", "선크림", "SUNSCREEN"),
        ]
        return [
            {
                "id": str(uuid4()),
                "position": position,
                "category_code": category_code,
                "product": {
                    "id": str(uuid4()),
                    "brand": brand,
                    "name": name,
                    "category_name": category_name,
                    "image_url": None,
                },
                "source": "AI_COMPOSED",
                "is_removed": False,
                "is_replacement": False,
                "purchased": False,
            }
            for position, (brand, name, category_name, category_code) in enumerate(
                products, start=1
            )
        ]

    def reorder(self, session: DemoSession, routine_id: str, requested: list[dict]) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"REVIEW_REQUIRED"})
        existing_ids = {item["id"] for item in routine["items"]}
        requested_ids = {item["routine_item_id"] for item in requested}
        positions = [item["position"] for item in requested]
        if (
            requested_ids != existing_ids
            or len(requested_ids) != len(requested)
            or len(set(positions)) != len(positions)
        ):
            raise ApiError(422, "INVALID_ROUTINE_ORDER", "전체 루틴 항목을 중복 없이 보내주세요.")
        position_map = {item["routine_item_id"]: item["position"] for item in requested}
        for item in routine["items"]:
            item["position"] = position_map[item["id"]]
        routine["items"].sort(key=lambda item: item["position"])
        routine["updated_at"] = utc_now()
        return self._routine_detail(routine)

    def confirm(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"REVIEW_REQUIRED"})
        routine["status"] = "CONFIRMED"
        routine["updated_at"] = utc_now()
        self.record_event(session, "routine_review_completed", {"routine_id": routine_id})
        return self._routine_detail(routine)

    def analyze(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"CONFIRMED", "ANALYSIS_FAILED"})
        routine["status"] = "ANALYZING"
        analysis_items = []
        for item in routine["items"]:
            product_name = item["product"]["name"]
            if "BHA 2%" in product_name:
                score, verdict = 22, "REMOVE"
                recommendation_id = str(uuid4())
                recommendation = {
                    "id": recommendation_id,
                    "required_single_step": True,
                    "decision": None,
                    "replacement_product": {
                        "id": AAC_PRODUCT_ID,
                        "brand": "AAC",
                        "name": "AAC 세이프 BHA 세럼",
                        "score": 91,
                        "price": 48000,
                        "image_url": None,
                    },
                    "comparison": {
                        "improved_ingredients": ["판테놀", "병풀추출물"],
                        "excluded_ingredients": ["에탄올", "향료"],
                    },
                }
                reasons = ["민감 피부에 자극 가능성이 있는 성분이 포함되어 있습니다."]
                flagged = [{"name": "에탄올", "reason": "민감도 악화 가능", "severity": "HIGH"}]
            elif "MISSHA" in item["product"]["brand"]:
                score, verdict, recommendation = 22, "CHOICE", None
                reasons = [
                    "현재 피부 상태에서는 여러 활성 성분을 함께 사용하는 빈도를 조절해주세요."
                ]
                flagged = [{"name": "향료", "reason": "자극 가능", "severity": "MEDIUM"}]
            else:
                score, verdict, recommendation = 82, "KEEP", None
                reasons = ["현재 피부 상태와 루틴 단계에 적합한 제품입니다."]
                flagged = []
            analysis_items.append(
                {
                    "routine_item_id": item["id"],
                    "score": score,
                    "verdict": verdict,
                    "reasons": reasons,
                    "flagged_ingredients": flagged,
                    "recommendation": recommendation,
                }
            )
        routine["analysis"] = {
            "routine_id": routine_id,
            "overall_score": 68,
            "summary": {"total": len(routine["items"]), "unsuitable": 2},
            "items": analysis_items,
            "analysis_version": "demo-v1",
            "model_version": "prompt-pending",
            "disclaimer": DISCLAIMER,
        }
        routine["status"] = "DECISION_REQUIRED"
        routine["updated_at"] = utc_now()
        return self._complete_job("SUITABILITY", routine_id)

    def get_analysis(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        if routine["analysis"] is None:
            raise ApiError(404, "ANALYSIS_NOT_FOUND", "적합도 분석 결과가 아직 없습니다.")
        self.record_event(session, "analysis_viewed", {"routine_id": routine_id})
        return routine["analysis"]

    def decide(
        self,
        session: DemoSession,
        routine_id: str,
        recommendation_id: str,
        decision: str,
    ) -> dict:
        routine = self._require_routine(session, routine_id)
        self._require_state(routine, {"DECISION_REQUIRED"})
        target_analysis = next(
            (
                item
                for item in routine["analysis"]["items"]
                if item.get("recommendation") and item["recommendation"]["id"] == recommendation_id
            ),
            None,
        )
        if target_analysis is None:
            raise ApiError(404, "RECOMMENDATION_NOT_FOUND", "교체 추천을 찾을 수 없습니다.")
        recommendation = target_analysis["recommendation"]
        if recommendation["decision"] is not None:
            raise ApiError(409, "RECOMMENDATION_ALREADY_DECIDED", "이미 처리한 추천입니다.")
        recommendation["decision"] = decision
        original = next(
            item for item in routine["items"] if item["id"] == target_analysis["routine_item_id"]
        )
        original["is_removed"] = True
        if decision == "REPLACE":
            replacement = recommendation["replacement_product"]
            routine["items"].append(
                {
                    "id": str(uuid4()),
                    "position": original["position"],
                    "category_code": original["category_code"],
                    "product": {
                        "id": replacement["id"],
                        "brand": replacement["brand"],
                        "name": replacement["name"],
                        "category_name": "세럼",
                        "image_url": replacement["image_url"],
                    },
                    "source": "AAC_REPLACEMENT",
                    "is_removed": False,
                    "is_replacement": True,
                    "purchased": False,
                }
            )
            self._add_cart_item(session, routine_id, recommendation_id, replacement)
            self.record_event(
                session,
                "replacement_added",
                {"routine_id": routine_id, "recommendation_id": recommendation_id},
            )
        routine["status"] = "COMPLETED"
        routine["completed_at"] = utc_now()
        routine["updated_at"] = utc_now()
        return self.final_routine(session, routine_id)

    def final_routine(self, session: DemoSession, routine_id: str) -> dict:
        routine = self._require_routine(session, routine_id)
        items = [item.copy() for item in routine["items"] if not item["is_removed"]]
        items.sort(key=lambda item: (item["position"], 0 if item["is_replacement"] else 1))
        for position, item in enumerate(items, start=1):
            item["position"] = position
        return {
            "routine_id": routine_id,
            "status": routine["status"],
            "items": items,
            "cart_item_count": len(self.cart_items),
            "completed_at": iso(routine["completed_at"]),
        }

    def _add_cart_item(
        self, session: DemoSession, routine_id: str, recommendation_id: str, product: dict
    ) -> None:
        existing = next(
            (
                item
                for item in self.cart_items.values()
                if item["recommendation_id"] == recommendation_id
            ),
            None,
        )
        if existing:
            return
        item_id = str(uuid4())
        self.cart_items[item_id] = {
            "id": item_id,
            "diagnosis_code_id": session.diagnosis_code_id,
            "routine_id": routine_id,
            "recommendation_id": recommendation_id,
            "product": {
                "id": product["id"],
                "brand": product["brand"],
                "name": product["name"],
                "image_url": product["image_url"],
            },
            "unit_price": product["price"],
            "quantity": 1,
        }

    def cart(self, session: DemoSession) -> dict:
        items = [
            item
            for item in self.cart_items.values()
            if item["diagnosis_code_id"] == session.diagnosis_code_id
        ]
        response_items = []
        for item in items:
            output = {key: value for key, value in item.items() if key != "diagnosis_code_id"}
            output["line_total"] = item["unit_price"] * item["quantity"]
            response_items.append(output)
        total = sum(item["line_total"] for item in response_items)
        return {
            "items": response_items,
            "subtotal_amount": total,
            "total_amount": total,
            "currency": "KRW",
        }

    def update_cart_item(self, session: DemoSession, item_id: str, quantity: int) -> dict:
        item = self._require_cart_item(session, item_id)
        item["quantity"] = quantity
        return self.cart(session)

    def delete_cart_item(self, session: DemoSession, item_id: str) -> None:
        self._require_cart_item(session, item_id)
        del self.cart_items[item_id]

    def create_order(self, session: DemoSession, payment_method: str, return_url: str) -> dict:
        cart = self.cart(session)
        if not cart["items"]:
            raise ApiError(400, "CART_EMPTY", "장바구니가 비어 있습니다.")
        order_id = str(uuid4())
        now = utc_now()
        order = {
            "id": order_id,
            "diagnosis_code_id": session.diagnosis_code_id,
            "order_number": f"WL-{now:%Y%m%d}-{len(self.orders) + 1:04d}",
            "status": "PENDING_PAYMENT",
            "total_amount": cart["total_amount"],
            "currency": "KRW",
            "payment_method": payment_method,
            "payment_action": {"type": "DEEPLINK", "url": f"{return_url}?mock_order_id={order_id}"},
            "paid_at": None,
            "created_at": now,
        }
        self.orders[order_id] = order
        self.record_event(session, "checkout_started", {"order_id": order_id})
        return self._public_order(order)

    def get_order(self, session: DemoSession, order_id: str) -> dict:
        order = self.orders.get(order_id)
        if order is None or order["diagnosis_code_id"] != session.diagnosis_code_id:
            raise ApiError(404, "ORDER_NOT_FOUND", "주문을 찾을 수 없습니다.")
        if order["status"] == "PENDING_PAYMENT":
            order["status"] = "PAID"
            order["paid_at"] = utc_now()
            self.record_event(session, "payment_completed", {"order_id": order_id})
        return self._public_order(order)

    @staticmethod
    def _public_order(order: dict) -> dict:
        return {
            key: iso(value) if isinstance(value, datetime) else value
            for key, value in order.items()
            if key != "diagnosis_code_id"
        }

    def get_job(self, session: DemoSession, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if job is None:
            raise ApiError(404, "JOB_NOT_FOUND", "분석 작업을 찾을 수 없습니다.")
        self._require_routine(session, job["routine_id"])
        return job

    def _complete_job(self, job_type: str, routine_id: str) -> dict:
        job_id = str(uuid4())
        job = {
            "id": job_id,
            "type": job_type,
            "routine_id": routine_id,
            "status": "SUCCEEDED",
            "progress": 100,
            "error": None,
            "created_at": iso(utc_now()),
            "completed_at": iso(utc_now()),
        }
        self.jobs[job_id] = job
        return job

    def record_event(
        self, session: DemoSession, name: str, properties: dict, occurred_at: str | None = None
    ) -> None:
        if name not in self.allowed_events:
            raise ApiError(422, "INVALID_EVENT_NAME", f"허용되지 않은 이벤트입니다: {name}")
        self.events.append(
            {
                "name": name,
                "session_id": session.id,
                "diagnosis_code_id": session.diagnosis_code_id,
                "occurred_at": occurred_at or iso(utc_now()),
                "properties": properties,
            }
        )

    def _owned_routines(self, session: DemoSession) -> list[dict]:
        return [
            routine
            for routine in self.routines.values()
            if routine["diagnosis_code_id"] == session.diagnosis_code_id
        ]

    def _require_routine(self, session: DemoSession, routine_id: str) -> dict:
        routine = self.routines.get(routine_id)
        if routine is None:
            raise ApiError(404, "ROUTINE_NOT_FOUND", "루틴을 찾을 수 없습니다.")
        if routine["diagnosis_code_id"] != session.diagnosis_code_id:
            raise ApiError(403, "ROUTINE_FORBIDDEN", "다른 사용자의 루틴에는 접근할 수 없습니다.")
        return routine

    def _require_cart_item(self, session: DemoSession, item_id: str) -> dict:
        item = self.cart_items.get(item_id)
        if item is None or item["diagnosis_code_id"] != session.diagnosis_code_id:
            raise ApiError(404, "CART_ITEM_NOT_FOUND", "장바구니 상품을 찾을 수 없습니다.")
        return item

    @staticmethod
    def _require_state(routine: dict, allowed: set[str]) -> None:
        if routine["status"] not in allowed:
            raise ApiError(
                409, "ROUTINE_STATE_CONFLICT", "현재 루틴 상태에서는 실행할 수 없습니다."
            )

    @staticmethod
    def _routine_summary(routine: dict) -> dict:
        return {
            "id": routine["id"],
            "status": routine["status"],
            "diagnosis_id": routine["diagnosis_id"],
            "overall_score": routine["analysis"]["overall_score"] if routine["analysis"] else None,
            "product_count": len([item for item in routine["items"] if not item["is_removed"]]),
            "created_at": iso(routine["created_at"]),
            "completed_at": iso(routine["completed_at"]),
        }

    def _routine_detail(self, routine: dict) -> dict:
        summary = self._routine_summary(routine)
        return {
            **summary,
            "selected_category_codes": routine["selected_category_codes"],
            "product_inputs": routine["product_inputs"],
            "items": sorted(routine["items"], key=lambda item: item["position"]),
            "updated_at": iso(routine["updated_at"]),
        }


demo_store = DemoStore()
