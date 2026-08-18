# well less backend

FastAPI 기반 AAC 스킨케어 루틴 분석 API입니다.

## 최초 설정

```powershell
Copy-Item .env.example .env
uv sync
```

`.env`에 `OPENAI_API_KEY`를 직접 입력합니다. Supabase Secret Key가 필요한 관리자 기능을 구현할 때만 `SUPABASE_SECRET_KEY`를 추가합니다. 두 값은 Flutter에 넣거나 Git에 커밋하지 않습니다.

## 실행

```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Android 에뮬레이터에서 접근: `http://10.0.2.2:8000`

## 검사

```powershell
uv run ruff check .
uv run pytest -q
```

## 구조

```text
app/
├─ api/       # HTTP 라우트
├─ core/      # 환경 설정
├─ schemas/   # 요청·응답 모델
├─ services/  # 분석·AI·추천 비즈니스 로직
└─ main.py    # FastAPI 진입점
tests/        # API·서비스 테스트
```
