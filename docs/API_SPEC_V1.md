# well less API 명세 v1

- 상태: **프론트·백엔드 개발 기준으로 확정**
- 기준일: 2026-08-20
- Base URL: `/api/v1`
- 원본 계약: [`openapi/openapi-v1.yaml`](../openapi/openapi-v1.yaml)
- 기준 자료: 2026-08-20 기능명세서, PRD, 사용자 흐름, Figma `45:1551`

이 문서는 현재 디자인을 바꾸기 위한 문서가 아니다. Figma에 확정된 화면 순서와 상태를 서버 데이터 및 API 호출로 연결하기 위한 계약이다. 루틴은 오전·야간으로 나누지 않는 **단일 순서 루틴**이다.

## 1. 확정 원칙

| 항목 | 확정 내용 |
| --- | --- |
| 인증 | 회원가입·비밀번호 없이 WHS 개인 코드로 인증하고 앱 전용 세션을 발급한다. |
| 피부 진단 | 개인 코드에 연결된 최신 진단의 피부 타입, 3축, 상세 지표를 조회한다. |
| 제품 입력 | 선택한 카테고리별로 여러 제품을 등록할 수 있고, 제품당 사진은 1~3장이다. |
| 루틴 | AI가 단일 루틴을 구성하고 사용자가 순서를 바꾼 뒤 확정한다. |
| AI 처리 | 제품 식별, 루틴 구성, 적합도 분석은 비동기 작업으로 제공한다. OpenAI 모델이 바뀌어도 앱 계약은 유지한다. |
| 적합도 | 전체 점수, 제품별 점수, `KEEP`·`CHOICE`·`REMOVE`, 근거와 주의 성분을 반환한다. 의료 진단이 아님을 함께 표시한다. |
| 제거·교체 | 사용자는 제거 대상마다 `REMOVE` 또는 `REPLACE`를 결정한다. `REPLACE`는 최종 루틴 변경과 장바구니 추가를 한 트랜잭션에서 처리한다. |
| 구매 | 장바구니 수량·삭제, 주문 생성, 앱 내 결제 상태 조회를 제공한다. PG사가 미정이어도 `payment_action` 계약은 유지한다. |
| 이전 기록 | 완료된 루틴 목록과 당시의 최종 루틴 스냅샷을 조회한다. |
| 보안 | OpenAI 키와 Supabase Secret/Service Role 키는 백엔드에만 둔다. Flutter에는 Publishable Key만 둔다. |

## 2. 공통 규칙

### 인증 헤더

인증 성공 후 모든 보호 API에 다음 헤더를 보낸다.

```http
Authorization: Bearer <access_token>
```

개인 코드는 로그·분석 이벤트에 평문으로 남기지 않는다. 서버 저장 시 해시값을 사용한다.

### 응답 형태

성공한 단일 응답:

```json
{
  "data": {}
}
```

목록 응답:

```json
{
  "data": [],
  "meta": { "next_cursor": null }
}
```

오류 응답:

```json
{
  "error": {
    "code": "INVALID_PERSONAL_CODE",
    "message": "개인 코드를 확인해주세요.",
    "field": "personal_code",
    "retryable": false,
    "request_id": "req_01..."
  }
}
```

### 공통 HTTP 상태

| 상태 | 의미 |
| --- | --- |
| `200` | 조회·수정 성공 |
| `201` | 루틴·입력·주문 생성 성공 |
| `202` | AI 비동기 작업 접수 |
| `204` | 삭제·로그아웃 성공, 응답 본문 없음 |
| `400` | 잘못된 요청 또는 현재 상태에서 불가능한 동작 |
| `401` | 인증 실패·토큰 만료 |
| `403` | 다른 사용자의 리소스 접근 |
| `404` | 리소스 없음 |
| `409` | 중복 요청 또는 상태 충돌 |
| `413` | 이미지 용량 초과 |
| `422` | 필드 검증 실패 |
| `429` | 호출 제한 초과 |
| `500/502/503` | 서버·외부 AI·결제 연동 오류 |

결제, AI 실행, 제거·교체 결정처럼 중복 실행 위험이 있는 `POST`·`PUT`에는 `Idempotency-Key`를 사용한다.

## 3. 상태 모델

### 루틴 상태

```text
DRAFT
  -> COMPOSING
  -> REVIEW_REQUIRED
  -> CONFIRMED
  -> ANALYZING
  -> DECISION_REQUIRED
  -> COMPLETED
```

AI 실패 시 `COMPOSE_FAILED` 또는 `ANALYSIS_FAILED`가 되며 같은 실행 API로 재시도한다. `COMPLETED` 루틴은 이전 기록용 스냅샷으로 보존한다.

### 기타 상태

| 대상 | 상태 |
| --- | --- |
| 제품 입력 | `UPLOADED`, `IDENTIFYING`, `IDENTIFIED`, `NEEDS_REVIEW`, `FAILED` |
| 비동기 작업 | `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED` |
| 제품 판정 | `KEEP`, `CHOICE`, `REMOVE` |
| 교체 결정 | `REMOVE`, `REPLACE` |
| 주문 | `PENDING_PAYMENT`, `PAID`, `PAYMENT_FAILED`, `CANCELLED` |
| 결제 수단 | `KAKAO_PAY`, `NAVER_PAY`, `TOSS_PAY`, `CARD` |

## 4. 화면 흐름별 API

| 순서 | Figma 화면·사용자 동작 | API | 핵심 응답·효과 |
| ---: | --- | --- | --- |
| 1 | 개인 코드 입력·인증 | `POST /auth/code/verify` | 세션, 사용자, 최신 진단 ID |
| 2 | 메인 화면 | `GET /me/overview` | 최신 진단, 진행/완료 루틴, 이전 기록 수 |
| 3 | 피부 레포트: 타입·상세 분석 | `GET /diagnoses/{diagnosis_id}` | OSP, O/D/C 축, 상세 지표, 진단일 |
| 4 | 이전 기록 목록 | `GET /routines?status=COMPLETED` | 완료 루틴 목록 |
| 5 | 카테고리 선택 | `GET /product-categories` | 노출명, 아이콘 키, 기본 순서, 필수 여부 |
| 6 | 검사 시작 | `POST /routines` | `DRAFT` 루틴 생성, 선택 카테고리 저장 |
| 7 | 제품 사진 등록 | `POST /routines/{routine_id}/product-inputs` | 입력 ID, 이미지 경로, 업로드 상태 |
| 8 | 등록 제품 삭제 | `DELETE /routines/{routine_id}/product-inputs/{input_id}` | 입력과 미확정 이미지 제거 |
| 9 | AI 루틴 분석 버튼 | `POST /routines/{routine_id}/compose` | `202`, 작업 ID |
| 10 | 분석 중 화면 | `GET /jobs/{job_id}` | 진행률·완료/실패 여부 |
| 11 | AI 단일 루틴 확인 | `GET /routines/{routine_id}` | 식별 제품과 단일 순서 목록 |
| 12 | 드래그 순서 변경 | `PUT /routines/{routine_id}/items/order` | 전체 항목의 새 순서 저장 |
| 13 | 루틴 확정 | `POST /routines/{routine_id}/confirm` | 상태 `CONFIRMED` |
| 14 | 피부 적합도 분석 | `POST /routines/{routine_id}/suitability-analysis` | `202`, 작업 ID |
| 15 | 적합도 결과 | `GET /routines/{routine_id}/analysis` | 전체·제품별 점수, 판정, 근거, AAC 비교 후보 |
| 16 | 제거 또는 AAC 교체 | `PUT /routines/{routine_id}/recommendations/{id}/decision` | 최종 루틴 갱신; 교체 시 장바구니도 갱신 |
| 17 | 최종 루틴·이전 루틴 상세 | `GET /routines/{routine_id}/final` | 순서, 교체 여부, 구매 여부, 장바구니 수 |
| 18 | 장바구니 | `GET /cart` | 상품, 수량, 합계 |
| 19 | 수량 변경·삭제 | `PATCH /cart/items/{item_id}`, `DELETE /cart/items/{item_id}` | 합계 재계산 |
| 20 | 결제 요청 | `POST /orders` | 주문번호, 금액, 결제 진행 정보 |
| 21 | 결제 완료 확인 | `GET /orders/{order_id}` | 결제 상태·결제 시각; 결제 성공 시 루틴의 미구매 표시 해제 |
| 공통 | UI 노출·버튼 클릭 KPI | `POST /analytics/events/batch` | 클라이언트에서만 알 수 있는 이벤트 기록 |

## 5. 엔드포인트 목록

### 인증·홈

| Method | Path | 설명 | 인증 |
| --- | --- | --- | --- |
| `POST` | `/auth/code/verify` | 개인 코드 검증 및 세션 발급 | 불필요 |
| `POST` | `/auth/token/refresh` | 액세스 토큰 갱신 | Refresh Token |
| `POST` | `/auth/logout` | 현재 세션 폐기 | 필요 |
| `GET` | `/me/overview` | 메인 화면용 요약 조회 | 필요 |

`POST /auth/code/verify`

```json
{
  "personal_code": "WHS-2026-1234",
  "device_id": "installation-uuid"
}
```

```json
{
  "data": {
    "access_token": "...",
    "refresh_token": "...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": { "id": "uuid", "display_name": "사용자" },
    "latest_diagnosis_id": "uuid"
  }
}
```

### 진단·카테고리

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/diagnoses/{diagnosis_id}` | 피부 타입·3축·상세 지표 조회 |
| `GET` | `/product-categories` | 제품 등록 카테고리 조회 |

진단 상세에는 다음 데이터가 포함된다.

```json
{
  "data": {
    "id": "uuid",
    "diagnosis_code": "OSP",
    "diagnosed_at": "2026-08-15T09:30:00+09:00",
    "skin_type": {
      "code": "OSP",
      "name": "지성·민감·색소성",
      "summary": "피지 분비가 많고 외부 자극에 민감한 피부"
    },
    "axes": [
      { "code": "O_D", "selected": "O", "score": 72 },
      { "code": "S_R", "selected": "S", "score": 66 },
      { "code": "P_N", "selected": "P", "score": 61 }
    ],
    "metrics": [
      { "code": "PORE", "name": "모공", "score": 68, "level": "CAUTION" }
    ],
    "disclaimer": "본 결과는 의료적 진단이 아닙니다."
  }
}
```

### 루틴·제품 입력·AI

| Method | Path | 허용 상태 | 설명 |
| --- | --- | --- | --- |
| `POST` | `/routines` | - | 최신 진단과 선택 카테고리로 검사 생성 |
| `GET` | `/routines` | - | 이전 기록 또는 진행 중 루틴 목록 |
| `GET` | `/routines/{routine_id}` | 전체 | 현재 루틴·제품 입력·AI 구성 조회 |
| `POST` | `/routines/{routine_id}/product-inputs` | `DRAFT` | `multipart/form-data` 이미지 등록 |
| `DELETE` | `/routines/{routine_id}/product-inputs/{input_id}` | `DRAFT` | 등록 입력 삭제 |
| `POST` | `/routines/{routine_id}/compose` | `DRAFT`, `COMPOSE_FAILED` | 제품 식별 및 단일 루틴 구성 시작 |
| `PUT` | `/routines/{routine_id}/items/order` | `REVIEW_REQUIRED` | 사용자 지정 순서 저장 |
| `POST` | `/routines/{routine_id}/confirm` | `REVIEW_REQUIRED` | AI 루틴 확정 |
| `POST` | `/routines/{routine_id}/suitability-analysis` | `CONFIRMED`, `ANALYSIS_FAILED` | 적합도 분석 시작 |
| `GET` | `/jobs/{job_id}` | - | AI 작업 상태 조회 |

제품 사진 등록 형식:

```text
Content-Type: multipart/form-data
category_code = SERUM_ESSENCE_AMPOULE
client_product_id = optional-client-uuid
images = front.jpg
images = ingredients.jpg
```

- 허용 형식: JPEG, PNG, HEIC
- 제품당 1~3장, 장당 최대 10 MB
- 서버는 EXIF 위치 정보를 제거하고 Supabase Storage의 비공개 버킷에 저장한다.
- DB에는 바이너리가 아니라 `bucket`, `object_path`, `mime_type`, `size_bytes`를 저장한다.

순서 변경 요청은 누락·중복을 막기 위해 전체 목록을 보낸다.

```json
{
  "items": [
    { "routine_item_id": "uuid-1", "position": 1 },
    { "routine_item_id": "uuid-2", "position": 2 }
  ]
}
```

### 적합도·제거·AAC 교체

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/routines/{routine_id}/analysis` | 전체 점수, 제품별 판정, 근거, 비교 후보 조회 |
| `PUT` | `/routines/{routine_id}/recommendations/{recommendation_id}/decision` | 제거 또는 교체 확정 |
| `GET` | `/routines/{routine_id}/final` | 결정이 적용된 최종 루틴 조회 |

분석 결과의 핵심 구조:

```json
{
  "data": {
    "routine_id": "uuid",
    "overall_score": 68,
    "summary": { "total": 8, "unsuitable": 2 },
    "items": [
      {
        "routine_item_id": "uuid",
        "score": 42,
        "verdict": "REMOVE",
        "reasons": ["민감 피부에 자극 가능성이 있는 성분이 포함되어 있습니다."],
        "flagged_ingredients": [
          { "name": "성분명", "reason": "민감도 악화 가능", "severity": "HIGH" }
        ],
        "recommendation": {
          "id": "uuid",
          "required_single_step": true,
          "replacement_product": {
            "id": "uuid",
            "brand": "AAC",
            "name": "대체 제품",
            "score": 91,
            "price": 32000,
            "image_url": "short-lived-signed-url"
          },
          "comparison": {
            "improved_ingredients": ["..."],
            "excluded_ingredients": ["..."]
          }
        }
      }
    ],
    "disclaimer": "성분 및 피부 정보에 기반한 참고 결과이며 의료적 진단이 아닙니다."
  }
}
```

결정 요청:

```json
{ "decision": "REPLACE" }
```

- `REMOVE`: 기존 제품을 최종 루틴에서 제외한다.
- `REPLACE`: 기존 제품을 제외하고 추천 AAC 제품을 같은 단계에 넣으며 장바구니에도 추가한다.
- 같은 `Idempotency-Key`의 재요청은 장바구니 수량을 중복 증가시키지 않는다.
- 분석 대상이 여러 개면 각 추천에 차례로 결정하고, 미결정 추천이 없어질 때 루틴을 `COMPLETED`로 만든다.

### 장바구니·주문·결제

| Method | Path | 설명 |
| --- | --- | --- |
| `GET` | `/cart` | 현재 장바구니와 합계 조회 |
| `PATCH` | `/cart/items/{item_id}` | 수량 변경 |
| `DELETE` | `/cart/items/{item_id}` | 장바구니 상품 삭제 |
| `POST` | `/orders` | 장바구니 스냅샷으로 주문·결제 시작 |
| `GET` | `/orders/{order_id}` | 결제 결과 조회 |
| `POST` | `/payments/webhooks/{provider}` | 결제사 서버 콜백; 앱 호출 금지 |

주문 요청:

```json
{
  "payment_method": "KAKAO_PAY",
  "return_url": "wellless://orders/return"
}
```

주문 응답:

```json
{
  "data": {
    "id": "uuid",
    "order_number": "WL-20260820-0001",
    "status": "PENDING_PAYMENT",
    "total_amount": 32000,
    "currency": "KRW",
    "payment_method": "KAKAO_PAY",
    "payment_action": {
      "type": "DEEPLINK",
      "url": "provider-or-app-url"
    },
    "paid_at": null
  }
}
```

실제 PG사가 결정되기 전 개발 환경은 `PAYMENT_PROVIDER=mock`을 사용한다. Mock은 주문/화면 통합 테스트용이며 운영 결제로 간주하지 않는다. 운영에서는 금액과 결제 성공 여부를 앱 응답이 아니라 결제사 웹훅으로 검증한다.

### 분석 이벤트

```http
POST /analytics/events/batch
```

```json
{
  "events": [
    {
      "name": "replacement_viewed",
      "occurred_at": "2026-08-20T12:00:00Z",
      "session_id": "uuid",
      "properties": { "routine_id": "uuid", "recommendation_id": "uuid" }
    }
  ]
}
```

허용 이벤트 이름은 `code_verified`, `inspection_started`, `routine_review_completed`, `analysis_viewed`, `replacement_viewed`, `replacement_added`, `cart_viewed`, `checkout_started`, `payment_completed`로 제한한다. 코드 인증·주문·결제처럼 서버가 확실히 아는 이벤트는 서버가 직접 기록하며 클라이언트 중복 이벤트는 제거한다.

## 6. 핵심 오류 코드

| 코드 | HTTP | 처리 |
| --- | ---: | --- |
| `INVALID_PERSONAL_CODE` | 401 | 코드 오류 문구 표시 |
| `EXPIRED_PERSONAL_CODE` | 401 | 만료 안내 |
| `DIAGNOSIS_NOT_FOUND` | 404 | 진단 데이터 문의 안내 |
| `IMAGE_TOO_LARGE` | 413 | 재촬영·용량 축소 안내 |
| `UNSUPPORTED_IMAGE_TYPE` | 422 | 지원 형식 안내 |
| `PRODUCT_NOT_IDENTIFIED` | 422 | 재촬영 안내; 잘못 식별된 제품을 확정하지 않음 |
| `ROUTINE_STATE_CONFLICT` | 409 | 최신 루틴 재조회 |
| `AI_PROVIDER_UNAVAILABLE` | 503 | 재시도 버튼 제공 |
| `RECOMMENDATION_ALREADY_DECIDED` | 409 | 최신 분석·최종 루틴 재조회 |
| `CART_EMPTY` | 400 | 장바구니 화면 유지 |
| `PAYMENT_FAILED` | 402 | 실패 사유와 재시도 제공 |

## 7. AI 계약과 아직 남은 구현 결정

OpenAI 프롬프트·모델·점수 공식은 아직 확정하지 않아도 프론트 개발은 가능하다. 앱은 AI 제공자 응답을 직접 받지 않고 위 API의 정규화된 스키마만 사용한다.

반드시 구현 전에 확정할 항목:

1. 제품 마스터·전성분 원천 데이터와 AAC 추천 제품 목록
2. 피부 유형·측정값별 성분 가중치와 점수 산식
3. 식별 신뢰도 임계값 및 `NEEDS_REVIEW` 처리 화면 정책
4. 실제 결제 PG사, 결제 SDK, 환불·취소 범위
5. 사진·진단·주문 데이터 보관 기간 및 삭제 정책

AI 출력은 서버에서 JSON Schema로 검증한다. 모델 출력의 제품 ID·가격·성분을 신뢰하지 않고 DB의 제품 마스터와 다시 대조하며, 점수와 추천 근거에는 분석 규칙 버전(`analysis_version`)과 모델 버전(`model_version`)을 저장한다.

## 8. 완료 조건

- Flutter와 FastAPI가 `openapi/openapi-v1.yaml`을 같은 계약으로 사용한다.
- UI에 필요한 필드가 부족하면 구현에서 임의 필드를 만들지 않고 명세를 먼저 변경한다.
- 경로·필드 삭제 또는 의미 변경은 `/api/v2` 또는 명시적 마이그레이션으로 처리한다.
- Swagger에서 요청·응답 예제를 확인할 수 있어야 한다.
- OpenAI·Supabase 비밀 키가 앱 번들, Git, 응답, 로그에 포함되지 않아야 한다.
