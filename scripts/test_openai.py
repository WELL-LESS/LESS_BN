import asyncio

from app.services.openai_service import run_prompt


async def main():
    result = await run_prompt(
        prompt="사용자 질문에 한국어로 간단하게 답변하십시오.",
        input_data="연결 테스트입니다. 'OpenAI 연결 성공'이라고 답변해 주세요.",
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())