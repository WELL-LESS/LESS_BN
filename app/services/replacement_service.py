import json

from app.prompt.less_prompts_compact import PROMPT_4_SEARCH
from app.services.openai_service import run_prompt_with_web


async def search_replacement_candidates(
    profile_code: str,
    product_name: str,
    category: str,
    maximum_candidates: int = 3,
) -> dict:
    input_data = {
        "user_profile": {
            "profile_code": profile_code,
        },
        "replacement_target": {
            "product_name": product_name,
            "category": category,
        },
        "search_settings": {
            "maximum_candidates": maximum_candidates,
        },
    }

    result = await run_prompt_with_web(
        prompt=PROMPT_4_SEARCH,
        input_data=json.dumps(
            input_data,
            ensure_ascii=False,
        ),
    )

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {
            "status": "invalid_response",
            "raw_text": result,
        }