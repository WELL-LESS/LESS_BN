from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Form, Header, Query, Response, UploadFile, status

from app.api.dependencies import SessionDependency
from app.core.errors import ApiError
from app.schemas.api import (
    RecommendationDecisionRequest,
    RoutineCreateRequest,
    RoutineOrderRequest,
)
from app.services.storage import upload_product_scan
from app.services.store import store

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/heic", "image/heif"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_routine(payload: RoutineCreateRequest, session: SessionDependency) -> dict:
    return {
        "data": store.create_routine(
            session,
            payload.diagnosis_id,
            payload.category_codes,
        )
    }


@router.get("")
async def list_routines(
    session: SessionDependency,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict:
    return {
        "data": store.list_routines(session, status_filter),
        "meta": {"next_cursor": None},
    }


@router.get("/{routine_id}")
async def get_routine(routine_id: str, session: SessionDependency) -> dict:
    return {"data": store.get_routine(session, routine_id)}


@router.post("/{routine_id}/product-inputs", status_code=status.HTTP_201_CREATED)
async def add_product_input(
    routine_id: str,
    session: SessionDependency,
    category_code: Annotated[str, Form()],
    images: Annotated[list[UploadFile], File()],
    client_product_id: Annotated[str | None, Form()] = None,
) -> dict:
    if not 1 <= len(images) <= 3:
        raise ApiError(
            422, "INVALID_IMAGE_COUNT", "제품 사진은 1장부터 3장까지 등록할 수 있습니다."
        )

    stored_images = []
    input_id = str(uuid4())
    for index, image in enumerate(images, start=1):
        content_type = (image.content_type or "").lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise ApiError(
                422,
                "UNSUPPORTED_IMAGE_TYPE",
                "JPEG, PNG, HEIC 이미지만 등록할 수 있습니다.",
                field="images",
            )
        content = await image.read(MAX_IMAGE_BYTES + 1)
        if len(content) > MAX_IMAGE_BYTES:
            raise ApiError(413, "IMAGE_TOO_LARGE", "이미지는 장당 10MB 이하여야 합니다.")
        extension = (image.filename or "image.jpg").rsplit(".", maxsplit=1)[-1].lower()
        object_path = f"{routine_id}/{input_id}/{index}.{extension}"
        try:
            upload_product_scan(
                bucket="product-scans-original",
                object_path=object_path,
                content=content,
                mime_type=content_type,
            )
        except Exception as exc:
            raise ApiError(
                503,
                "STORAGE_PROVIDER_UNAVAILABLE",
                "이미지 저장소에 연결할 수 없습니다.",
                retryable=True,
            ) from exc
        stored_images.append(
            {
                "bucket": "product-scans-original",
                "object_path": object_path,
                "mime_type": content_type,
                "size_bytes": len(content),
                "original_filename": image.filename,
            }
        )
    result = store.add_product_input(
        session,
        routine_id,
        input_id,
        category_code,
        client_product_id,
        stored_images,
    )
    return {"data": result}


@router.delete(
    "/{routine_id}/product-inputs/{input_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product_input(
    routine_id: str,
    input_id: str,
    session: SessionDependency,
) -> Response:
    store.delete_product_input(session, routine_id, input_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{routine_id}/compose", status_code=status.HTTP_202_ACCEPTED)
async def compose_routine(
    routine_id: str,
    session: SessionDependency,
    _idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    return {"data": store.compose(session, routine_id)}


@router.put("/{routine_id}/items/order")
async def reorder_routine(
    routine_id: str,
    payload: RoutineOrderRequest,
    session: SessionDependency,
) -> dict:
    requested = [item.model_dump() for item in payload.items]
    return {"data": store.reorder(session, routine_id, requested)}


@router.post("/{routine_id}/confirm")
async def confirm_routine(routine_id: str, session: SessionDependency) -> dict:
    return {"data": store.confirm(session, routine_id)}


@router.post("/{routine_id}/suitability-analysis", status_code=status.HTTP_202_ACCEPTED)
async def start_suitability_analysis(
    routine_id: str,
    session: SessionDependency,
    _idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    return {"data": store.analyze(session, routine_id)}


@router.get("/{routine_id}/analysis")
async def get_suitability_analysis(routine_id: str, session: SessionDependency) -> dict:
    return {"data": store.get_analysis(session, routine_id)}


@router.put("/{routine_id}/recommendations/{recommendation_id}/decision")
async def decide_recommendation(
    routine_id: str,
    recommendation_id: str,
    payload: RecommendationDecisionRequest,
    session: SessionDependency,
    _idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    return {
        "data": store.decide(
            session,
            routine_id,
            recommendation_id,
            payload.decision.value,
        )
    }


@router.get("/{routine_id}/final")
async def get_final_routine(routine_id: str, session: SessionDependency) -> dict:
    return {"data": store.final_routine(session, routine_id)}
