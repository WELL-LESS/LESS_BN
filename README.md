# well less backend

FastAPI 기반 AAC 스킨케어 루틴 분석 API입니다.

## API 계약

- 사람용 명세: [`docs/API_SPEC_V1.md`](docs/API_SPEC_V1.md)
- 기계 판독 계약: [`openapi/openapi-v1.yaml`](openapi/openapi-v1.yaml)

현재 핵심 시연 흐름은 API v1 계약에 맞춰 구현되어 있습니다.

## 현재 MVP 동작 범위

- 개인 코드 인증 및 앱 전용 Bearer 세션
- 피부 진단 레포트와 제품 카테고리 조회
- 검사 생성, 제품 이미지 1~3장 등록, 단일 루틴 구성·순서 변경·확정
- 피부 적합도 결과(68점), 제거·AAC 교체 결정
- 최종 루틴, 장바구니, 수량 변경·삭제
- 카카오·네이버·토스·카드 모의 주문 및 결제 완료 확인
- 주요 분석 이벤트 수집

`SUPABASE_SECRET_KEY`가 설정되어 있으면 인증 세션, 검사, 제품 입력, 루틴, 분석 결과,
AAC 교체, 장바구니, 주문, 이벤트를 실제 Supabase DB에 저장합니다. 제품 이미지는
`product-scans-original` 비공개 버킷에 저장합니다.

Secret Key가 없는 로컬·CI 환경에서는 같은 API 계약의 결정론적 메모리 저장소로 자동 전환됩니다.
이 모드에서는 서버를 재시작하면 검사·장바구니·주문 데이터가 초기화됩니다. OpenAI 프롬프트가
연결되기 전까지 루틴 구성과 점수는 화면 연동용 결정론적 결과를 사용합니다.

시연용 개인 코드는 `WHS-2026-1234`입니다.

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

실제 Supabase 전체 흐름과 테스트 데이터 자동 정리:

```powershell
uv run python -m scripts.smoke_supabase
```

현재 핵심 사용자 흐름은 통합 테스트로 검증합니다.

```text
개인 코드 → 진단·카테고리 → 검사 생성 → 이미지 등록 → 루틴 구성
→ 순서 확정 → 적합도 분석 → AAC 교체 → 장바구니 → 모의 결제
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
