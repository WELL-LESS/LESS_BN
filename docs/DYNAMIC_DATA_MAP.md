# 동적 프론트 데이터 연결 기준

Flutter는 화면 표시 상태와 애니메이션만 관리합니다. 피부 진단, 제품, 루틴,
분석 결과, 장바구니 데이터는 백엔드 API를 통해 조회하며 Supabase Secret Key와
OpenAI API Key는 앱에 넣지 않습니다.

| 화면/기능 | API 데이터 | Supabase 저장 위치 | 이미지 저장 위치 |
| --- | --- | --- | --- |
| 개인 코드 입력 | 세션, 최신 진단 ID | `diagnosis_codes`, `access_sessions` | 없음 |
| 피부 진단 레포트 | O/D/C 및 12유형, 진단 점수, 설명 | `skin_type_families`, `skin_types`, `skin_diagnoses`, `diagnosis_metrics` | 비공개 `diagnosis-reports` |
| 카테고리 선택 | 카테고리명과 순서 | `product_categories` | 없음 |
| 제품 촬영 | 촬영 상태, 원본·누끼 이미지 경로 | `product_scans`, `product_scan_images` | 비공개 `product-scans-original`, `product-scans-cutout` |
| AI 루틴 확인 | 제품, 카테고리, 순서 | `routine_sessions`, `routine_items`, `products` | 공개 `product-catalog` 또는 촬영 이미지 서명 URL |
| 적합도 분석 | 전체/제품 점수, KEEP·CHOICE·REMOVE, 근거 | `product_analyses`, `routine_sessions.score_breakdown` | 제품 이미지와 동일 |
| AAC 교체 | 추천 제품, 성분 비교, 사용자 결정 | `replacement_recommendations`, `products`, `product_ingredients` | 공개 `product-catalog` |
| 최종 루틴 | 활성 제품과 최종 순서 | `routine_items` | 제품 이미지와 동일 |
| 장바구니·모의 결제 | 가격, 수량, 결제수단, 결제상태 | `carts`, `cart_items`, `orders`, `order_items` | 공개 `product-catalog` |

## OpenAI 연결 직전 준비된 계약

- 입력: 진단 ID/피부 유형/측정값, `scan_id`, 카테고리, 비공개 이미지의 단기
  서명 URL, 사용자가 확정한 루틴 순서
- 출력: `app/schemas/ai.py`의 버전별 구조화 응답
- 실행 기록: `ai_analysis_runs`에 모델, 프롬프트 버전, 입력·출력 JSON, 토큰,
  지연시간, 오류를 기록
- 플랫폼 프롬프트: `.env`의 `OPENAI_PROMPT_ID`, `OPENAI_PROMPT_VERSION`을
  실행 이력의 `provider_prompt_id`, `provider_prompt_version`에 복사
- 이미지 추적: `ai_analysis_run_images`에 각 실행에서 실제 사용한 원본 또는
  누끼 이미지와 해상도 옵션을 기록
- 안전 경계: AI는 DB 제품 ID, 판매가, AAC 추천 제품을 만들지 않습니다.
  백엔드가 검증된 DB 제품 중에서 최종 교체 제품과 가격을 선택합니다.

OpenAI 프롬프트가 확정되면 `prompt_version`과 구조화 출력 스키마 버전을 함께
올려, 이전 분석 결과를 재현할 수 있게 합니다.
