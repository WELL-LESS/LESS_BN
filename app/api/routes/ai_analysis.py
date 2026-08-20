import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile

from app.api.dependencies import SessionDependency
from app.core.config import settings
from app.core.errors import ApiError
from app.prompt.less_prompts_compact import PROMPT_2, PROMPT_3
from app.services.openai_service import run_product_image_prompt, run_prompt
from app.services.store import store

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGES = 10
IMAGE_TYPES_BY_EXTENSION = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def _parse_json(raw: str, stage: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ApiError(
            502,
            "AI_INVALID_RESPONSE",
            f"OpenAI {stage} 응답이 올바른 JSON 형식이 아닙니다.",
            retryable=True,
        ) from exc
    if not isinstance(parsed, dict):
        raise ApiError(502, "AI_INVALID_RESPONSE", f"OpenAI {stage} 응답 형식이 잘못되었습니다.")
    return parsed


def _product_view(raw: dict, index: int) -> dict:
    analysis = raw.get("product_analysis") or {}
    breakdown = analysis.get("score_breakdown") or {}
    name = analysis.get("product_name") or raw.get("product_name") or f"촬영 제품 {index + 1}"
    score = int(breakdown.get("final_score") or analysis.get("final_score") or 0)
    primary = analysis.get("matched_primary_targets") or []
    optional = analysis.get("optional_matches") or []
    ingredients = [
        str(item.get("ingredient"))
        for item in [*primary, *optional]
        if isinstance(item, dict) and item.get("ingredient")
    ]
    return {
        "name": name,
        "brand": raw.get("brand") or analysis.get("brand"),
        "category": raw.get("category") or analysis.get("category") or "스킨케어",
        "description": analysis.get("analysis_summary") or "피부 진단 기준으로 분석된 제품입니다.",
        "individual_score": max(0, min(100, score)),
        "ingredients": ingredients[:6],
        "analysis": analysis,
    }


@router.post("/analyze-routine")
async def analyze_routine(
    routine_id: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()],
    session: SessionDependency,
) -> dict:
    if not 1 <= len(images) <= MAX_IMAGES:
        raise ApiError(
            422, "INVALID_IMAGE_COUNT", "제품 사진은 1장부터 10장까지 등록할 수 있습니다."
        )

    routine = store.get_routine(session, routine_id)
    overview = store.overview(session)
    latest_diagnosis = overview.get("latest_diagnosis") or {}
    profile_code = latest_diagnosis.get("diagnosis_code")
    if not profile_code:
        raise ApiError(404, "DIAGNOSIS_NOT_FOUND", "피부 진단 결과를 찾을 수 없습니다.")
    if not routine.get("product_inputs"):
        raise ApiError(400, "PRODUCT_INPUT_REQUIRED", "저장된 제품 사진이 없습니다.")

    image_inputs: list[tuple[bytes, str]] = []
    for image in images:
        content_type = (image.content_type or "").lower()
        extension = (image.filename or "").rsplit(".", maxsplit=1)[-1].lower()
        if content_type in {"", "application/octet-stream"}:
            content_type = IMAGE_TYPES_BY_EXTENSION.get(extension, content_type)
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise ApiError(
                422, "UNSUPPORTED_IMAGE_TYPE", "JPG, PNG, WEBP 이미지만 사용할 수 있습니다."
            )
        content = await image.read(MAX_IMAGE_BYTES + 1)
        if not content:
            raise ApiError(422, "EMPTY_IMAGE", "빈 이미지 파일은 분석할 수 없습니다.")
        if len(content) > MAX_IMAGE_BYTES:
            raise ApiError(413, "IMAGE_TOO_LARGE", "이미지는 장당 10MB 이하여야 합니다.")
        image_inputs.append((content, content_type))

    try:
        product_raw_texts = await asyncio.gather(
            *(
                run_product_image_prompt(
                    prompt=PROMPT_2,
                    profile_code=profile_code,
                    image_bytes=content,
                    content_type=content_type,
                )
                for content, content_type in image_inputs
            )
        )
        product_results = [
            _parse_json(raw, f"제품 {index + 1} 분석")
            for index, raw in enumerate(product_raw_texts)
        ]

        routine_input = {
            "ruleset_version": "LESS_SIX_INGREDIENTS_1.1",
            "user_profile": {"profile_code": profile_code},
            "products": [result.get("product_analysis") or result for result in product_results],
        }
        routine_result = _parse_json(
            await run_prompt(
                prompt=PROMPT_3,
                input_data=json.dumps(routine_input, ensure_ascii=False),
            ),
            "루틴 분석",
        )
    except ApiError:
        raise
    except Exception as exc:
        raise ApiError(
            502,
            "AI_PROVIDER_ERROR",
            f"OpenAI 분석에 실패했습니다: {type(exc).__name__}",
            retryable=True,
        ) from exc

    products = [_product_view(result, index) for index, result in enumerate(product_results)]
    routine_analysis = routine_result.get("routine_analysis") or {}
    penalty = routine_analysis.get("penalty_breakdown") or {}
    overall_score = int(penalty.get("final_score") or routine_analysis.get("final_score") or 0)
    remove_candidates = routine_analysis.get("remove_candidates") or []

    response_data = {
        "profile_code": profile_code,
        "routine_id": routine_id,
        "model": settings.openai_model,
        "products": products,
        "routine": [
            {
                "position": index + 1,
                "name": product["name"],
                "category": product["category"],
                "description": product["description"],
            }
            for index, product in enumerate(products)
        ],
        "overall_score": max(0, min(100, overall_score)),
        "summary": routine_analysis.get("summary")
        or "촬영한 제품 루틴의 피부 적합도 분석 결과입니다.",
        "remove_candidates": remove_candidates,
        "ruleset_version": routine_result.get("ruleset_version") or "LESS_SIX_INGREDIENTS_1.1",
    }
    analysis_run = store.record_ai_analysis_result(
        session,
        routine_id,
        input_payload={
            "profile_code": profile_code,
            "image_count": len(image_inputs),
            "ruleset_version": response_data["ruleset_version"],
        },
        output_payload=response_data,
    )
    response_data["analysis_run_id"] = analysis_run["id"]
    return {"data": response_data}
