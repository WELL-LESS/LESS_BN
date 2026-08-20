from uuid import uuid4

from app.schemas.routine import (
    ProductAnalysisResult,
    ProductStatus,
    RoutineAnalysisRequest,
    RoutineAnalysisResponse,
    RoutineProductInput,
    RoutineStep,
    UsageTime,
)
from app.services.demo_data import AAC_REPLACEMENTS, DEMO_DIAGNOSIS

CATEGORY_ORDER = {
    "CLEANSER": 10,
    "TONER": 20,
    "ESSENCE": 30,
    "SERUM": 40,
    "AMPOULE": 50,
    "CREAM": 60,
    "SUNSCREEN": 70,
}

DISCLAIMER = "이 결과는 피부 진단이나 치료를 대신하지 않는 참고용 분석입니다."


def _analyze_product(product: RoutineProductInput) -> ProductAnalysisResult:
    normalized = {ingredient.strip().lower() for ingredient in product.ingredients}
    caution_hits = [
        ingredient
        for ingredient in DEMO_DIAGNOSIS.caution_ingredients
        if ingredient.lower() in normalized
    ]
    recommended_hits = [
        ingredient
        for ingredient in DEMO_DIAGNOSIS.recommended_ingredients
        if ingredient.lower() in normalized
    ]
    score = max(0, min(100, 80 + len(recommended_hits) * 5 - len(caution_hits) * 20))
    reasons = [f"주의 성분 '{ingredient}'이 포함되어 있어요." for ingredient in caution_hits]
    reasons.extend(
        f"권장 성분 '{ingredient}'이 포함되어 있어요." for ingredient in recommended_hits
    )
    if not reasons:
        reasons.append("현재 등록된 피부·성분 규칙에서 특별한 충돌이 발견되지 않았어요.")

    if score < 60:
        result_status = ProductStatus.replace
    elif score < 80:
        result_status = ProductStatus.caution
    else:
        result_status = ProductStatus.keep

    replacement_id = None
    if result_status == ProductStatus.replace:
        replacement_id = AAC_REPLACEMENTS.get(product.category.upper())

    return ProductAnalysisResult(
        product_id=product.product_id,
        score=score,
        status=result_status,
        reasons=reasons,
        replacement_product_id=replacement_id,
    )


def _routine_steps(products: list[RoutineProductInput], usage: UsageTime) -> list[RoutineStep]:
    applicable = [product for product in products if product.usage in {usage, UsageTime.both}]
    ordered = sorted(applicable, key=lambda item: CATEGORY_ORDER.get(item.category.upper(), 999))
    return [
        RoutineStep(
            order=index,
            product_id=product.product_id,
            name=product.name,
            category=product.category,
        )
        for index, product in enumerate(ordered, start=1)
    ]


def analyze_routine(payload: RoutineAnalysisRequest) -> RoutineAnalysisResponse:
    results = [_analyze_product(product) for product in payload.products]
    overall_score = round(sum(result.score for result in results) / len(results))
    return RoutineAnalysisResponse(
        analysis_id=str(uuid4()),
        overall_score=overall_score,
        morning_routine=_routine_steps(payload.products, UsageTime.morning),
        night_routine=_routine_steps(payload.products, UsageTime.night),
        product_results=results,
        disclaimer=DISCLAIMER,
    )
