import base64
import json

from openai import AsyncOpenAI

from app.core.config import settings


def _client() -> AsyncOpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        max_retries=3,
        timeout=120.0,
    )


# Prompt 1~3 일반 텍스트 실행
async def run_prompt(
    prompt: str,
    input_data: str,
) -> str:
    response = await _client().responses.create(
        model=settings.openai_model,
        instructions=prompt,
        input=input_data,
    )

    return response.output_text


# Prompt 4 웹 검색 포함 실행
async def run_prompt_with_web(
    prompt: str,
    input_data: str,
) -> str:
    response = await _client().responses.create(
        model=settings.openai_model,
        instructions=prompt,
        tools=[{"type": "web_search"}],
        input=input_data,
    )

    return response.output_text


# Prompt 2 제품 사진 분석 및 웹 검색 실행
async def run_product_image_prompt(
    prompt: str,
    profile_code: str,
    image_bytes: bytes,
    content_type: str,
) -> str:
    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    input_text = json.dumps(
        {
            "user_profile": {"profile_code": profile_code},
            "request": (
                "사진에서 브랜드와 정확한 제품명을 확인하십시오. "
                "웹 검색으로 해당 제품의 전체 전성분과 출처 URL을 찾고, "
                "확인된 전성분을 Prompt 2 규칙으로 분석하십시오. "
                "제품을 정확히 식별할 수 없으면 추측하지 말고 "
                "insufficient_data를 출력하십시오."
            ),
        },
        ensure_ascii=False,
    )

    response = await _client().responses.create(
        model=settings.openai_model,
        instructions=prompt,
        tools=[{"type": "web_search"}],
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": input_text,
                    },
                    {
                        "type": "input_image",
                        "image_url": (f"data:{content_type};base64,{encoded_image}"),
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    return response.output_text
