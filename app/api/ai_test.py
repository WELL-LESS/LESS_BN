import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from app.services.replacement_service import (
    search_replacement_candidates,
)
from app.prompt.less_prompts_compact import (
    PROMPT_1,
    PROMPT_2,
    PROMPT_3,
    PROMPT_4,
    PROMPT_4_SEARCH,
)
from app.services.openai_service import (
    run_product_image_prompt,
    run_prompt,
    run_prompt_with_web,
)


router = APIRouter(tags=["AI Test"])
class PromptTestRequest(BaseModel):
    input_data: dict
    
class ReplacementSearchRequest(BaseModel):
    profile_code: str
    product_name: str
    category: str
    maximum_candidates: int = 3
    


PROMPTS = {
    1: PROMPT_1,
    2: PROMPT_2,
    3: PROMPT_3,
    4: PROMPT_4,
}


# Prompt 1~4 텍스트 JSON 테스트
@router.post("/ai/test/prompt/{prompt_number}")
async def test_prompt(
    prompt_number: int,
    request: PromptTestRequest,
):
    prompt = PROMPTS.get(prompt_number)

    if prompt is None:
        raise HTTPException(
            status_code=400,
            detail="prompt_number는 1부터 4까지만 가능합니다.",
        )

    input_json = json.dumps(
        request.input_data,
        ensure_ascii=False,
    )

    try:
        if prompt_number == 4:
            combined_prompt = (
                PROMPT_2
                + "\n\n"
                + PROMPT_3
                + "\n\n"
                + PROMPT_4
            )

            result = await run_prompt_with_web(
                prompt=combined_prompt,
                input_data=input_json,
            )
        else:
            result = await run_prompt(
                prompt=prompt,
                input_data=input_json,
            )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ) from error

    try:
        parsed_result = json.loads(result)
    except json.JSONDecodeError:
        parsed_result = {
            "raw_text": result
        }

    return {
        "prompt_number": prompt_number,
        "result": parsed_result,
    }


# Prompt 2 제품 이미지 분석 테스트
@router.post("/ai/test/product-image")
async def test_product_image(
    profile_code: str = Form(...),
    image: UploadFile = File(...),
):
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="JPG, PNG, WEBP 이미지만 업로드할 수 있습니다.",
        )

    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="이미지 파일이 비어 있습니다.",
        )

    try:
        result = await run_product_image_prompt(
            prompt=PROMPT_2,
            profile_code=profile_code,
            image_bytes=image_bytes,
            content_type=image.content_type,
        )

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ) from error

    try:
        parsed_result = json.loads(result)
    except json.JSONDecodeError:
        parsed_result = {
            "raw_text": result
        }

    return {
        "filename": image.filename,
        "profile_code": profile_code,
        "result": parsed_result,
    }

@router.post("/ai/test/replacement/search")
async def test_replacement_search(
    request: ReplacementSearchRequest,
):
    try:
        result = await search_replacement_candidates(
            profile_code=request.profile_code,
            product_name=request.product_name,
            category=request.category,
            maximum_candidates=request.maximum_candidates,
        )

        return result

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {str(error)}",
        ) from error