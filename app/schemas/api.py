from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DataResponse(BaseModel):
    data: dict


class CodeVerifyRequest(BaseModel):
    personal_code: str = Field(min_length=4, max_length=32)
    device_id: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20)


class RoutineCreateRequest(BaseModel):
    diagnosis_id: str
    category_codes: list[str] = Field(min_length=1)


class RoutineOrderItem(BaseModel):
    routine_item_id: str
    position: int = Field(ge=1)


class RoutineOrderRequest(BaseModel):
    items: list[RoutineOrderItem] = Field(min_length=1)


class RecommendationDecision(StrEnum):
    remove = "REMOVE"
    replace = "REPLACE"


class RecommendationDecisionRequest(BaseModel):
    decision: RecommendationDecision


class CartQuantityRequest(BaseModel):
    quantity: int = Field(ge=1, le=99)


class PaymentMethod(StrEnum):
    kakao_pay = "KAKAO_PAY"
    naver_pay = "NAVER_PAY"
    toss_pay = "TOSS_PAY"
    card = "CARD"


class OrderCreateRequest(BaseModel):
    payment_method: PaymentMethod
    return_url: str


class AnalyticsEvent(BaseModel):
    name: str
    occurred_at: datetime
    session_id: str | None = None
    properties: dict = Field(default_factory=dict)


class AnalyticsBatchRequest(BaseModel):
    events: list[AnalyticsEvent] = Field(min_length=1, max_length=100)
