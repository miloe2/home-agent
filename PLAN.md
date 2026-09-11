# 내집마련 분석 백엔드 구현 계획

## 0. 문서의 권한과 구현 범위

- 원본 요구사항: `REQUIREMENTS.md`. 본 문서는 이를 실행 가능한 설계로 구체화한다. 요구사항과 충돌하면 원본을 우선하고 차이를 기록한다.
- 초기 상태: 요구사항과 빈 계획 파일만 있는 신규 Python 프로젝트. 이 문서는 설계 산출물이며 구현 완료를 의미하지 않는다.
- 필수 완료 범위: Phase 1~2. 서버 실행, mock 수집, 비교 분석, 규칙 기반 판단, 한국어 보고서, 파일 저장, 테스트가 끝까지 동작해야 한다.
- 선택 범위: Phase 3의 청약Home·LH 실연결. 공식 명세와 키가 확보되는 경우에만 구현한다. 연결 실패로 Phase 1~2 완료를 막지 않는다.
- Phase 4~6은 인터페이스와 확장 지점을 준비하지만 실연결 구현은 후속 작업이다. MVP에서 모든 분석 항목은 mock 또는 명시적인 데이터 부족 상태로 표현한다.
- 프론트엔드, 알림, DB/ORM, 인증, 사용자 관리, 큐, 멀티에이전트, 필수 LLM 의존성은 추가하지 않는다.
- 원문 첫머리는 마지막의 ‘비싼 모델에게 요청할 작업’을 참조하지만 제공된 파일에는 해당 제목의 별도 절이 없다. 제공된 전체 요구사항과 ‘실제 구현 없이 상세 계획 작성’을 기준으로 설계했다.
- 아래 점수 가중치·판정 문턱·비교 허용 범위는 **초기 제품 규칙**이다. 시장에서 검증된 예측모형이나 금융기관 규정이 아니다. `analysis_rules.yaml`에서 조정 가능하게 만든다.

## 1. 아키텍처와 핵심 원칙

```text
FastAPI / Python analyze_property()
        ↓
입력·프로필 검증 → 단지/주택형 식별 → source adapters
                                      ↓
                           정규화된 사실 + 근거 + 결측/충돌
                                      ↓
취득비용 / 이력 / 기존거래 / 신규분양 / 대체재 / 입지 / 금융 분석
                                      ↓
                    사용자 적합성 → 점수 → verdict
                                      ↓
                한국어 템플릿 보고서 → JSON 파일 저장
```

외부 I/O는 sources와 storage에 한정한다. 분석 함수는 정규화한 데이터와 설정을 입력받는 순수 함수로 작성한다. FastAPI 의존성이 분석 로직 안으로 들어가지 않게 한다. 실연결과 mock은 동일한 인터페이스를 구현한다.

판단 원칙:

1. `살 수 있는가`는 비용·금융 분석, `살 만한가`는 상품·시장·사용자 적합성 분석으로 분리한다.
2. 관측 사실, 규칙에 따른 해석, 미확인 가설을 구별한다. ‘왜 이 가격인가’의 원인을 입증할 자료가 없으면 가설과 추가 확인사항으로 답한다.
3. 결측은 0이나 ‘문제없음’이 아니다. 빈 검색 결과도 ‘미분양 없음’, ‘더 나은 대안 없음’을 뜻하지 않는다.
4. mock 데이터로 실제 매수 추천을 하지 않는다. 점수와 판정은 계산하되 `simulation_only=true`와 보고서 첫 줄의 모의분석 표시를 유지한다.
5. 서울 주소 자체에는 가점을 주지 않고 경기 주소 자체에는 감점을 주지 않는다. 확인된 생활편의·접근성·상품성으로 평가한다.
6. SH 잔여 거주기간 10년은 사용자 제공 가정이다. 자격·기간을 공적으로 확인했다고 표현하지 않는다.
7. 모든 시간 기준은 실행 시 주입한 `as_of`를 사용한다. 테스트는 고정 시계를 사용한다.

## 2. 기술 선택과 실행 형태

- Python 3.11 이상, FastAPI, Uvicorn, Pydantic v2, pydantic-settings, PyYAML, httpx.
- 개발 의존성: pytest, pytest-asyncio, respx(HTTP 모킹), Ruff. 표준 라이브러리 `decimal`, `hashlib`, `pathlib`, `json`, `uuid`, `datetime`, `statistics` 활용.
- XML 공식 API 연결이 필요할 때만 `defusedxml` 추가. 임의 크롤러·브라우저 자동화·벡터DB는 도입하지 않는다.
- `pyproject.toml`에 버전 범위를 선언하고 구현 환경에서 검증한 lock 파일을 한 종류만 커밋한다. 설치된 최신 버전을 가정한 API를 사용하지 않는다.
- 기본 주소는 `127.0.0.1:8000`. CORS는 기본 비활성. 개인 금융정보와 보고서는 로컬에만 저장한다.
- 환경변수: `HOME_AGENT_SOURCE_MODE=mock|live`, `HOME_AGENT_DATA_DIR`, `HOME_AGENT_CONFIG_DIR`, 선택적 공급자 키. `.env.example`에 빈 키만 제공한다.
- `live`에서 키가 없거나 실패하면 `unavailable`로 반환한다. mock으로 조용히 전환하지 않는다. mock과 live를 소스별로 섞는 설정은 초기 버전에서 제공하지 않는다.

## 3. 파일 구조와 책임

```text
home-agent/
  REQUIREMENTS.md
  PLAN.md
  README.md
  pyproject.toml
  .env.example
  .gitignore
  config/
    user_profile.yaml
    finance_rules.yaml
    analysis_rules.yaml
  src/home_agent/
    __init__.py
    main.py                    # app factory, lifespan에서 의존성 생성
    settings.py                # 환경변수·경로 검증
    api/routes.py              # HTTP 변환, 분석 로직 없음
    schemas/
      common.py                # 근거, 측정값, 상태, finding
      property.py              # 입력, 단지 식별, 비용
      profile.py               # 사용자·금융·정책·분석 설정
      market.py                # 거래, 분양이력, 입지, 비교후보
      analysis.py              # 섹션별 결과와 최종 AnalysisResult
    services/
      analyze.py               # 전체 실행 조정
      identity.py              # 단지/주택형 식별과 충돌 처리
      normalize.py             # 금액·날짜·면적 정규화
    sources/
      base.py                  # Protocol, query, SourceResult
      applyhome.py
      lh.py
      molit_transactions.py
      kapt.py
      geocoding.py
      transit.py
      web_search.py
      mock.py                  # fixture 기반 동일 인터페이스 구현
      registry.py              # 모드별 어댑터 조립
      http_client.py           # timeout, 재시도, cache
    analysis/
      costs.py
      sale_history.py
      comparables.py
      new_supply.py
      alternatives.py
      location.py
      finance.py
      user_fit.py
      scoring.py
      verdict.py
      confidence.py
    reporting/
      renderer.py              # 결정론적 한국어 Markdown
    storage/
      cache.py                 # JSON HTTP 응답 캐시
      reports.py               # JSON 보고서 저장/조회
  data/
    fixtures/                  # 공개 가능하고 명시적으로 합성된 테스트 자료
    cache/                     # gitignore
    reports/                   # gitignore
  tests/
    conftest.py
    unit/
    integration/
    fixtures/                  # API 응답 형식 검증용 샘플 등
```

과도한 범용 repository 계층은 만들지 않는다. `JsonReportStore.save/get_latest`와 `JsonHttpCache.get/set`의 작은 인터페이스만 두면 추후 교체할 수 있다.

## 4. 입력과 프로필 계약

### 4.1 PropertyInput

필수: `name: str`(공백 제거 후 1~200자), `unit_type: str`(1~40자).

선택: `region`, `address`, `exclusive_area_m2`, `price_krw`, `official_property_id`, `sale_notice_id`. 금액은 양의 정수 KRW, 면적은 양의 유한 Decimal이다. `bool`을 금액으로 허용하지 않는다. 알 수 없는 필드는 금지한다.

원문 예제의 최소 입력을 모두 허용한다. `unit_type="38"`에서 면적 38㎡를 자동 확정하지 않는다. 주택형 명칭과 실제 전용면적은 별개다. 가격·면적이 끝내 확인되지 않아도 식별 가능한 후보는 부분 분석을 반환한다.

사용자 입력의 가격·면적은 **사용자가 평가하려는 조건**으로 보존한다. 공식 문서와 값이 다르면 입력을 덮어쓰지 않고 `conflicts`에 양쪽 근거와 값을 넣는다. 잘못된 주택형 연결 가능성이 있는 핵심 충돌은 가격 판정과 긍정 verdict를 막는다.

### 4.2 프로필

`config/user_profile.yaml`에는 REQUIREMENTS.md의 프로필을 값과 의미 그대로 옮긴다. 추가 필드는 nullable로 둔다:

- `finance.annual_gross_income_krw`, `reported_business_income_krw`, `net_assets_krw`, `available_cash_krw`, `existing_monthly_debt_payment_krw`.
- `finance.marriage_date`, `household_member_count`, `citizenship`, `age` 등은 실제 정책에서 필요할 때 명시적으로 요구한다. 초기 버전에서 수집을 강제하지 않는다.
- 근로소득과 사업소득을 단순 합산하지 않는다. 금융기관이 요구하는 소득 산정방식이 확인되지 않으면 관련 입력 부족으로 처리한다.

프로필 검증은 enum, 숫자 범위와 교차 조건을 확인한다: `preferred_max <= stretch_max`, `strong_penalty_below <= acceptable_min <= ideal`, `ideal_commute <= acceptable_commute`, `remaining_stable_housing_years >= 0`. 무주택/생애최초 등의 자기신고는 대출 승인 증명이 아니다.

`POST /profile/validate`는 파일을 수정하지 않는다. 잘못된 서버 설정은 startup에서 경로와 필드명만 포함한 오류로 실패시키며 금융정보 값을 로그에 출력하지 않는다.

## 5. 공통 데이터 모델과 근거 연결

모든 스키마는 Pydantic으로 정의하고 `schema_version="1.0"`을 출력한다. 내부 면적·비율 계산은 Decimal, 금액 합산은 정수 KRW로 한다. JSON의 면적·비율은 유한 number로 직렬화하고 금액은 integer로 유지한다. timestamp는 UTC ISO 8601, 날짜만 확인되는 공고는 `date`와 `date_precision`을 사용한다.

| 모델 | 필수 계약 |
| --- | --- |
| `Evidence` | `id`, `source_url`, `fetched_at`, `source_type`, `adapter`, `is_mock`, 선택적 `published_at`, `effective_from/to`, `locator`, `excerpt`, `raw_cache_key` |
| `Fact[T]` | `value: T|null`, `status: known|missing|conflicting`, `evidence_ids`, 선택적 `as_of`; known에는 근거가 필수 |
| `Finding` | `code`, `kind: fact|interpretation|hypothesis|missing_information`, `text`, `evidence_ids`, `rule_id`, `severity: info|positive|caution|critical` |
| `SourceResult[T]` | `status: ok|partial|unavailable|error|not_applicable`, `items`, `evidence`, `warnings`, `queried_at`, `query_scope` |
| `Conflict` | `field`, `candidate_values`와 각각의 evidence, `resolution`, `blocks_sections` |

`source_type`: `official_api|official_document|institution|news|web|user_input|mock`. 사용자 입력은 `user://property-input`, 프로필은 `user://profile`, 모의 자료는 `fixture://case-a/...` URI를 쓴다. 공식 URL처럼 꾸미지 않는다. 외부자료는 가능한 한 상세 공고·원문 URL을 보존하며 검색결과 페이지를 원문으로 대체하지 않는다.

근거는 최종 결과의 `evidence[]`에 중복 제거해 보관한다. 데이터 항목과 finding은 ID로 참조한다. 계산값에는 입력 근거와 `rule_id`를 연결한다. 보고서의 주요 주장에는 `[E001]` 형태로 표시하고 끝에 출처·수집일을 렌더링한다.

우선순위는 같은 대상·주택형·시점을 비교할 때 공식 공고/API → 공식 기관자료 → 뉴스 → 일반 웹이다. 서로 다른 시점의 가격은 충돌 대신 이력일 수 있다. 사용자 입력은 별도 시나리오 조건으로 유지한다. 상충하는 공식 자료는 단순 최신 수집순으로 확정하지 않는다.

`NormalizedProperty`는 다음을 Fact로 가진다: 공식명, 주소, 시도/시군구, 단지 ID, 주택종류, 건설사, 세대수, 동수, 입주일/예정일, 준공연도, 전용/공급면적, 방/욕실, 분양가, 확장비, 필수옵션비, 좌표. `property_type` 제외 대상이면 수집을 최소화하고 사용자 부적합으로 `pass`; 알 수 없는 종류는 확인 필요다.

## 6. Source adapter와 데이터 식별

### 6.1 공통 호출 계약

`SourceContext`: `as_of`, `mode`, 주입된 http client/cache, 분석 실행 ID. `QueryScope`에는 대상 ID/행정구역/기간/반경/페이지 수/완결 여부를 기록한다.

비동기 Protocol 메서드:

| 소스 | 메서드 | 정규화 반환값 |
| --- | --- | --- |
| ApplyHome / LH | `search_properties(query, ctx)`, `fetch_notices(property_ref, ctx)`, `search_new_supply(area_query, ctx)` | 단지 후보 / 공고·분양 사건 / 신규분양 후보 |
| MOLIT | `fetch_transactions(region_code, year_month, ctx)` | 아파트 매매 거래 |
| KAPT | `fetch_complex(property_ref, ctx)` | 단지 기본정보 |
| Geocoding | `geocode(address, ctx)`, `nearby_places(geo_query, ctx)` | 좌표 / 역·시설 |
| Transit | `route(origin, destination, depart_at, ctx)` | 이동수단별 시간·도보·환승·기준시각 |
| WebSearch | `search(query, ctx)` | URL·제목·발행일·발췌·검색 범위 |

원래 API가 특정 정보를 제공하지 않으면 반환값을 만들어 채우지 않는다. `capabilities`로 지원 범위를 선언한다. MVP의 live 미구현 소스는 명시적 unavailable을 반환하고, mock 구현은 네 케이스 fixture를 반환한다.

### 6.2 식별 순서

1. 공식 ID가 있으면 우선 조회한다.
2. 없으면 정규화한 단지명과 지역/주소로 후보를 찾는다. 이름 정규화는 공백·표기 별칭 정도만 수행한다.
3. 이름이 같아도 주소/사업 ID가 다르면 다른 단지로 유지한다. 공식 ID도 공급자 namespace와 함께 저장한다.
4. 후보 2개 이상에서 확정할 근거가 없으면 HTTP 409 `ambiguous_property`, 후보명/주소/ID를 반환한다. 첫 검색 결과를 선택하지 않는다.
5. 검색 자체가 불가능하지만 이름과 사용자 입력만 있는 경우 `identity_status=unresolved`, 입력만을 이용한 부분 분석을 허용한다. 외부 거래를 임의 연결하지 않는다.
6. `unit_type`은 공고 주택형에 정확히 연결한다. 면적 유사성만으로 다른 주택형의 가격·옵션을 섞지 않는다.

### 6.3 캐시·실패 처리

- 키: 공급자 + 정규화 endpoint + 비밀키를 제외한 쿼리 + adapter schema version의 SHA-256. API key가 포함된 URL/헤더를 캐시·근거·로그에 남기지 않는다.
- 캐시 envelope: `fetched_at`, `expires_at`, HTTP status, content type, JSON body 또는 XML/text body 문자열. HTTP 응답 전체를 JSON으로 감싼다.
- 초기 TTL: 공고/거래 24시간, 단지·좌표 30일, 교통·웹검색 24시간. 설정으로 변경 가능하다. 정책의 유효성은 캐시 TTL과 별도로 검증한다.
- 만료 캐시는 기본 사용하지 않는다. 향후 사용 옵션을 추가하면 반드시 stale 상태를 전달한다.
- 연결 5초, 읽기 15초, 소스 작업 전체 30초, 분석 전체 90초. 독립 소스는 동시 실행하되 동시 HTTP 요청 최대 4개.
- 네트워크 일시 실패/429/5xx만 최대 2회 재시도한다. Retry-After는 남은 기한 안에서만 따른다. 인증·권한·형식 오류는 반복하지 않는다.
- 성공 응답만 정상 캐시에 저장한다. 파싱 실패, API 오류 envelope, 미완료 pagination은 성공으로 취급하지 않는다.
- 외부 호출 실패는 해당 섹션의 부족정보로 전파한다. 잘못된 코드·스키마 불변식 오류까지 catch-all로 ‘데이터 부족’으로 숨기지 않는다.

## 7. 비용 분석: 가격·총비용·자기자금 구분

`analyze_costs(property, cost_inputs) -> PriceAnalysis`

```text
effective_price = 분양가 + 발코니 확장비 + 필수 옵션비
total_acquisition_cost = effective_price + 취득 관련 세금 + 등기/법무비
                         + 해당 거래에 실제 발생하는 기타 취득비용
required_equity = total_acquisition_cost - 확인된 사용 가능 대출액
```

- 중개료는 실제 발생 대상일 때만 포함한다. 초기 분양에 일괄 적용하지 않는다.
- 금리·취득세율·LTV·대출한도를 임의로 하드코딩하지 않는다. 초기 버전은 사용자 입력 또는 검증된 설정값만 계산한다.
- 누락 비용이 있으면 `effective_price`/`total_acquisition_cost`를 확정하지 않는다. `known_cost_subtotal`, `missing_cost_items`, `is_complete=false`를 반환한다. 미확인 항목을 0원으로 넣지 않는다.
- `required_equity`는 확정 입력이 없으면 null. 대출 시나리오를 입력받게 확장하더라도 승인액이 아니라 가정이라고 표시한다.
- 계약금·중도금·잔금 일정이 있으면 `payment_schedule[]`에 날짜/금액/근거를 저장한다. 일정이 없으면 초기 납부 현금의 충분 여부를 판단하지 않는다.
- 6억/7억 예산 평가는 사용자 희망 가격구간이며 금융상품 자격 기준과 다르다. 분양가 기준 범위와 총취득비용 확인 여부를 함께 보여준다.
- 단가 `price_per_exclusive_m2`는 보조값이다. 소형·대형 단가를 선형 변환해 적정가를 만들지 않는다.

## 8. 분양이력 분석

`build_sale_history(events, property_ref, as_of) -> SaleHistoryAnalysis`

`SaleEvent`: `id`, 단지/공고/주택형 ID, `event_type`, `event_date`, `date_precision`, `round`, `units`, `price_krw`, `competition_ratio`, `benefits`, `evidence_ids`.

event_type은 `initial_sale|competition_result|contract_result|unsold|unranked|discretionary|first_come|resupply|discount|benefit_added`. 동일 공고의 재게시·뉴스 인용은 별도 재공급으로 세지 않는다. 공고 ID 또는 단지+사건종류+발생일+차수로 중복 제거하고 모든 출처는 보존한다.

- 시간순 정렬, 미상 날짜는 끝에 분리. 발표일과 공급/계약 사건일을 구분한다.
- 최초 분양가와 최신 가격은 같은 주택형·포함옵션·조건일 때만 증감을 계산한다.
- `>=2`개의 서로 다른 후속 공급 사건이면 `repeated_supply_signal=true`. 같은 가격대가 12개월 이상 지속됐다는 해석은 가격·기간이 모두 확인될 때만 한다.
- 보고 문구: ‘반복 재공급은 당시 조건에서 수요 흡수가 원활하지 않았을 가능성을 시사한다.’ 계약취소 등 다른 사유가 있으면 병기한다.
- 시장금리·시장상황·입주 조건 자료가 없으면 그 원인을 단정하지 않고 ‘배경 자료 미확인’으로 남긴다.
- 반복공급 자체로 `avoid`를 내리지 않는다. 전량 완판 주장에는 공식 계약/공급 결과 등 근거가 필요하다.

## 9. 기존 아파트 비교 알고리즘

`select_comparables(target, transactions, complex_metadata, rules, as_of) -> ComparableAnalysis`

### 9.1 거래 정제

- 아파트 매매만 포함한다. 전월세·오피스텔·분양권을 섞지 않는다.
- 계약일 기준 최근 12개월 우선. 부족하면 최대 24개월로 확장하고 확장 사실을 표시한다. 미래 거래일은 제외한다.
- 해제/취소 거래는 제외하고 사유를 남긴다. 중복 키는 공식 거래 ID 우선, 없으면 단지+계약일+면적+층+금액이며 충돌 가능성을 기록한다.
- 신고 지연·공급자 조회 범위·미완료 pagination을 기록한다. 아직 신고되지 않은 거래까지 있다고 가정하지 않는다.
- 직거래 여부, 층수, 특수 조건은 유지한다. 비정상적 거래를 단순 가격만으로 삭제하지 않는다. 표본이 충분할 때 IQR 이상치를 표시하되 원본·제외 기준·민감도 결과를 보존한다.

### 9.2 생활권과 비교군

생활권은 확인된 역세권/행정동/명시적 생활권 매핑을 사용한다. 좌표만 있으면 1km부터 최대 3km까지 후보를 넓히되 `distance_proxy`라고 표시한다. 거리만으로 같은 생활권이라고 확정하지 않는다. 좌표가 없으면 행정구역 후보로 한정하고 공간 비교 불확실성을 남긴다.

서로 겹칠 수 있는 네 그룹을 반환한다:

| 그룹 | 초기 규칙 | 용도 |
| --- | --- | --- |
| `same_area` | 전용면적 차이 <= max(5㎡, 대상면적×15%) | 직접 가격 비교 |
| `larger_area` | 대상보다 최소 8㎡ 큼, 49/59/74/84㎡ 기준 다음 최대 2개 면적대의 ±5㎡ | 같은 돈의 면적 기회비용 |
| `new_or_recent` | 분석 기준 준공 0~10년 | 신축 프리미엄 비교 |
| `representative_old` | 준공 15년 이상, 비교 생활권 거래량 상위 | 대표 구축 대안 |

각 그룹은 조건에 해당하는 실제 표본만 반환한다. 표본이 없는 그룹을 가짜 후보로 채우지 않는다. 11~14년 단지도 다른 그룹에는 들어갈 수 있다. 37㎡의 larger_area는 49㎡와 59㎡ 부근 후보를 우선한다.

선정 우선순위는 `(확인된 동일생활권, 동일역세권, 면적차, 연식차, 세대수차, 거래최신성, 거리)`의 사전식 순서다. 알려지지 않은 속성은 일치로 간주하지 않는다. 그룹별 최대 5단지, 단지·면적군별 거래 요약을 반환한다. 각 후보에 `selection_reasons`, `differences`, `missing_fields`를 남긴다.

### 9.3 가격 판정

- 단지별 동일 면적군의 최근 실거래 min/max/median, 표본수, 거래기간을 계산한다. 최솟값~최댓값은 관측 범위이며 신뢰구간이 아니다.
- 직접 판정에는 same_area 중 동일 생활권이 확인되고 연식 차이 <=10년인 비교군만 쓴다. 최소 2단지·3거래가 없으면 `insufficient_information`.
- 비교 기준가격은 단지별 median의 median으로 한다. 거래가 많은 한 단지가 기준가격을 지배하지 않게 한다.
- 대상 분양가는 기존 실거래와 비교하되 `comparison_basis=base_sale_price_vs_resale_transaction`을 명시한다. 옵션을 포함한 실질가격 비율은 별도로 계산한다. 옵션 미확인 시 분양가 기준 결론은 `provisional=true`다.
- `ratio=target_base_price/reference_median`: <=0.90 `cheap`, <=1.05 `fair`, <=1.15 `fair_to_expensive`, 그 초과 `expensive`. 이 문턱은 평가 가정이고 통계적 적정가 보증이 아니다.
- 신축·대단지·역 접근성 차이는 프리미엄의 가능한 설명으로 제시하되, 검증 없이 원화 프리미엄을 가산해 적정가를 만들지 않는다.
- larger_area 및 구축 비교는 포기하는 면적/연식을 설명하는 데 쓴다. 이를 동일상품 가격비교처럼 사용하지 않는다.

## 10. 최근 신규분양과 대체재

### 10.1 신규분양

`compare_new_supply(target, supplies, transactions, rules, as_of)`

- 최근 3년 우선, 부족하면 5년까지 확장한다. 지역 및 인접 생활권을 검색하고 검색 범위를 반환한다.
- 후보는 단지명/위치/분양연도/주택형/면적/당시 분양가/확장비 포함 여부/현재 실거래/세대수/역거리/공급이력/근거를 가진다.
- ‘현재 실거래’는 연결 가능한 실제 계약만 사용하고 계약일을 표시한다. 미입주·거래 없음은 null이다.
- 서로 다른 주택형·층의 당시 분양가와 현재 거래가로 수익률을 확정하지 않는다. 동일 조건 연결이 확인되면 명목 변화율과 비교 한계를 출력한다.
- 과거 분양은 당시 시장의 참고자료다. 현재 매수 가능한 대안 목록과 분리한다.

### 10.2 대체재

`rank_alternatives(target, candidate_properties, profile, rules)`

- 서울/경기 아파트, 선호 예산 6억 이하 우선, 최대 7억 이내. 현재 후보보다 비싼 대안에는 추가금액을 반드시 표시한다.
- 인접 생활권을 먼저 탐색하고, 사용자 관심 지역/통근 가능 지역을 추가한다. 검색 범위는 configuration으로 관리하고 ‘전 수도권 최선’이라고 주장하지 않는다.
- 후보를 단지+주택형+가격시점 기준으로 중복 제거한다. 비교군에서 얻은 후보 재사용 가능.
- `availability=confirmed_current_supply|historical_transaction_reference|unknown`. 실거래 기록은 현재 매물이나 구매 가능성의 증거가 아니다.
- 면적, 가격, 통근, 세대수, 연식별 `gains`와 `tradeoffs`를 반환한다. 통근 미확인은 통근 우위로 취급하지 않는다.
- 알려진 모든 핵심 축에서 나쁘지 않고 하나 이상 우수할 때만 `dominates_target=true`; 핵심 축이 빠지면 `undetermined`.
- 알려진 면적 하한 충족 여부 → 예산 → 통근 → 단지규모/연식 순으로 후보 정렬한다. 최대 5개, 각 선정 이유를 함께 반환한다.
- 결과가 없으면 ‘조회 범위 안에서 확인된 대안 없음’. ‘대안이 없다’는 결론은 금지한다.

## 11. 입지·통근 분석

`analyze_location(property, places, routes, developments, profile)`

- 최근접역, 도보거리/시간, 상권·병원·학교·마트는 값과 근거를 각각 보관한다. 직선거리와 실제 도보거리를 구분한다.
- 통근은 출발지 문앞 → 도보/대기/환승 → 직장 문앞 기준. 경로 제공자가 대기시간 등을 포함하지 않으면 총 door-to-door 확정값으로 표시하지 않는다.
- workplace_address=null이면 `commute.status=insufficient_information`, 점수도 null. 서울 중심/강남 접근시간은 참고 destination이며 사용자 출퇴근시간을 대체하지 않는다.
- 미래 교통망 상태는 `planned|approved|groundbreaking|under_construction|opening_confirmed|operating|unknown`. ‘착공식’과 실제 공사를 구분하고 기준일·출처를 표시한다.
- 현재 통근 점수에는 운행 중인 경로만 반영한다. 미래 계획은 별도 시나리오 설명으로만 사용한다.
- 시설 자료가 부족하면 입지를 나쁘다고 단정하지 않는다. 세부 시설 종합점수는 MVP에서 만들지 않고 finding으로 제공한다.

## 12. 정책대출 설계

`evaluate_finance(property, profile, finance_rules, as_of) -> PolicyFinanceAnalysis`

현재 정책 금액·금리·한도를 이 계획에서 확정하지 않는다. 구현 시 현재 날짜에 유효한 공식 주택도시기금/한국주택금융공사 자료를 확인해야 한다. 검색 요약·블로그·과거 fixture는 현재 규칙의 source of truth가 아니다.

`finance_rules.yaml`의 각 상품 규칙:

```yaml
schema_version: '1.0'
programs:
  - id: didimdol
    verification_status: unverified
    verified_at: null
    effective_from: null
    effective_to: null
    recheck_after: null
    source_urls: []
    required_fields: []
    conditions: []
  - id: bogeumjari
    verification_status: unverified
    verified_at: null
    effective_from: null
    effective_to: null
    recheck_after: null
    source_urls: []
    required_fields: []
    conditions: []
```

실제 조건은 `field`, `operator`, `value`, `applicability`, `evidence_id`의 선언형 규칙으로 표현한다. operator는 `eq|lte|gte|in`, applicability는 검증된 조건 조합만 허용한다. YAML 문자열을 eval하지 않는다. `first_time_homebuyer`와 `newlywed`는 관심 조건/우대 유형이며 별도 대출상품이라고 임의 생성하지 않는다.

평가 순서:

1. 미검증, 시행일 미확인, 적용기간 밖, 재확인 기한 경과, 공식 출처 없음 → `insufficient_information`.
2. 검증된 필수 조건에서 확인된 불충족 → `not eligible`, 불충족 조건을 명시한다.
3. 핵심 소득/자산/가구 입력 누락 → `insufficient_information`, 충족한 주택 조건은 별도로 반환한다.
4. 필수 조건은 충족하지만 조건부 예외의 적용 확인이 남으면 `possibly eligible`.
5. 설정에 명시된 모든 적용 필수 조건이 확인·충족되면 `likely eligible`. 승인·대출액 확정 의미는 아니다.

외부 JSON status는 원문대로 `likely eligible|possibly eligible|not eligible|insufficient_information`을 사용한다. 내부 enum 명칭은 snake_case 가능하다. 결과에는 `checked_conditions`, `missing_fields`, `rules_version`, `rule_sources`, `approval_confirmed=false`, `approved_amount_krw=null` 포함.

MVP 기본 설정은 unverified가 정상이다. 테스트의 가짜 정책은 별도 fixture에 `is_mock=true`로 두고 live 금융규칙으로 로드하지 않는다. Case C의 6.7억이 정책상 불리하다는 테스트는 **가상의 가격상한 규칙**을 사용한 모의 검증으로 한정한다.

## 13. 사용자 적합성과 10개 질문

`analyze_user_fit(property, sections, profile) -> UserFitAnalysis`

`good[]`, `bad[]`, `unresolved[]`, `questions[]`를 반환한다. questions는 원문 H의 10개 질문을 고정 ID `Q1`~`Q10`으로 모두 포함한다. 각 답변은 `answer`, `status: supported|partial|unknown`, `evidence_ids`, `rule_ids`, `what_to_verify`를 가진다.

고정 질문 문구:

1. 왜 이 가격인가?
2. 이 가격이 싼가, 적정한가, 비싼가?
3. 싼다면 왜 싼가?
4. 비싸다면 어떤 프리미엄 때문인가?
5. 사용자가 이 집을 사면 무엇을 얻는가?
6. 무엇을 포기하는가?
7. SH에서 10년 기다릴 수 있는 사용자가 지금 살 정도로 좋은가?
8. 5~10년 실거주에 적합한가?
9. 향후 다른 사람이 사고 싶어할 상품인가?
10. 같은 돈으로 더 좋은 대안이 있는가?

- 왜 이 가격인가/싸거나 비싼 이유: 비교자료와 확인된 상품 차이를 연결한다. 확인되지 않은 개발·할인 이유는 hypothesis다.
- 무엇을 얻고 포기하는가: 면적, 연식, 위치, 예산, 통근, 단지규모를 구체적으로 대조한다.
- 지금 살 필요가 있는가: 사용자 입력의 낮은 긴급성과 확인된 대안/상품 타협을 연결한다. 기다리면 반드시 더 싸진다는 예측은 하지 않는다.
- 5~10년 거주: 면적·방구조·출퇴근·가족구성 변화 가능성을 다루되 출산 계획을 가정하지 않는다.
- 향후 매도수요: 거래 표본·상품범용성·공급이력을 근거로 장단점을 설명한다. 가격상승·매도 성공 확률을 생성하지 않는다.

기계적으로 ‘서울 신축이라 장점’만 반복하지 않는다. 기본적인 사용자 선호와 실제 시장 가격매력은 별개 finding으로 유지한다.

## 14. 보조 점수와 verdict

### 14.1 점수

각 component는 `id`, `weight`, `value: 0..100|null`, `reasoning`, `evidence_ids`를 반환한다.

| 항목 | 가중치 | 초기 점수 규칙 |
| --- | ---: | --- |
| 면적 | 30 | <40㎡:10 / 40~<50:40 / 50~<59:80 / >=59:100 |
| 예산 | 20 | 가격<=6억:100 / <=7억:50 / >7억:0; 프로필 예산으로 치환 |
| 시장 가격매력 | 20 | cheap:100 / fair:75 / fair_to_expensive:40 / expensive:10 / 미확인:null |
| 통근 | 15 | <=40분:100 / <=60:70 / >60:10; 프로필 문턱 사용 |
| 단지규모 | 10 | <150세대:20 / 150~<300:50 / 300~<500:75 / >=500:100 |
| 연식 | 5 | 신축·준공<=5년:100 / <=10:80 / <=20:60 / 그 외:40 |

준공예정 신축은 신축 선호 점수를 주되 입주시기/확정성은 별도 리스크로 유지한다. 모르는 값은 점수 null. 프로필 임계값은 평가 시작 시 정규화한 rules에 적용한다.

`coverage_weight=sum(알려진 component 가중치)`, `total=sum(value*weight)/coverage_weight`를 소수 첫째 자리로 표시한다. coverage가 60 미만이면 total=null. 점수에는 `provisional`, `coverage_weight`를 반드시 함께 출력한다. coverage 60은 계산 가능 기준일 뿐 추천 가능 기준이 아니다.

금융 적합성은 별도 결과이며 좋은 집 점수를 부풀리는 가점으로 넣지 않는다. 세부 인프라도 근거 없는 임의 점수로 합치지 않는다.

### 14.2 verdict 우선순위

순서대로 평가하고 `rule_hits`와 `blocked_promotions`를 남긴다:

1. 공식 근거로 해당 대상의 중대한 구조적 위험이 확인됨 → `avoid`. 초기 코드에서 지원하는 위험은 `confirmed_sale_fraud`, `confirmed_occupancy_prohibition` 같은 명시적 코드만 허용한다. 일반 뉴스 단어 검색이나 미분양 횟수로 생성하지 않는다. MVP mock에서만 검증해도 된다.
2. 제외 주택종류/지역, 가격>stretch 예산, 면적<40㎡, 확인된 통근>60분 중 하나 → `pass`. 초기 프로필의 큰 타협을 표현한다. 누락값에는 적용하지 않는다.
3. 식별 미해결, 핵심 충돌, 필수 판단정보 부족 → `watch`. 이미 확인된 1~2번 사유는 결측 때문에 완화하지 않는다.
4. `strong_buy_candidate`: total>=85, coverage=100, confidence>=0.85, 면적>=59㎡, 가격<=선호예산, 가격판정 cheap이며 provisional 아님, 통근<=40분, 총취득비용 완결, 자금조달 검토 입력 충분, 주요 미해결 위험 없음, 이력·대체재 조사 완료, 확인된 우월 대안 없음.
5. `consider`: total>=70, coverage>=85, confidence>=0.70, 면적>=50㎡, 가격<=stretch, 통근<=60분, 가격판정 cheap 또는 fair이며 provisional 아님, 주요 비용·식별·이력 충돌 없음. 금융 입력이 없으면 ‘자금계획 확인 전 검토 후보’로 제한한다.
6. 나머지는 `watch`.

3번의 필수 판단정보는 식별, 전용면적, 가격, 가격비교, 통근, 중요 추가비용이다. 4~5번은 긍정 후보가 되는 추가 조건이며 점수만으로 통과할 수 없다. 낮은 가격점수만으로 avoid를 만들지 않는다. 면적 기준을 넘겼어도 대체재/이력 경고는 보고서에 반드시 반영한다.

mock 실행에서도 동일한 규칙과 confidence 조건을 적용하므로 실제 API 응답은 watch/pass/avoid 범위다. 긍정 verdict 분기는 순수 함수 단위 테스트에서 완결된 평가 입력과 confidence를 주입해 검증한다. live에서 부적합(pass) 판단은 확실하지만 시장 설명은 부족할 수 있으므로 두 정보를 분리해 설명한다.

### 14.3 confidence

confidence는 **분석 근거 충실도**이며 추천 성공확률이 아니다.

영역 가중치: 식별/상품 0.20, 취득비용 0.15, 공급이력 0.15, 기존거래 0.20, 신규분양/대안 0.10, 입지/통근 0.10, 금융 0.10.

각 영역은 required field coverage × source quality × freshness × conflict factor로 0~1을 산출한다. 품질은 공식 1.0, 기관 0.9, 사용자입력 0.7, 뉴스 0.6, 일반 웹 0.4, mock 0.0. 같은 사실을 여러 URL에서 가져왔다고 합산하지 않는다. 동일 원문 재인용도 신뢰도 증가로 쓰지 않는다.

- completeness는 다음 필수 항목 중 충족한 비율이다. 식별/상품: 단지 식별·주택형·면적·세대수·연식. 취득비용: 분양가·확장비·필수옵션·세금/부대비용. 공급이력: 최초 공급 확인·후속 공고 조회 완결. 기존거래: 생활권 확인·최소 표본 충족·기간 내 거래. 신규분양/대안: 신규분양 조회 완결·대안 조회 완결. 입지/통근: 역 접근성·실제 직장 경로. 금융: 유효한 정책·적용 필수 사용자 입력. 항목별 동일 가중치를 사용한다. 조회 완결은 검색 범위 내 완결일 뿐 시장 전체 완전성을 뜻하지 않는다.
- 영역 source quality/freshness는 충족 항목마다 근거의 최고 품질/해당 자료 freshness를 구한 뒤 항목 간 평균을 사용한다. 미충족 항목은 completeness에서 반영하므로 중복 감점하지 않는다. 충족 항목이 없으면 영역 0. conflict factor는 미해결 충돌 0, 그 외 1. 최종 confidence는 영역 점수의 가중합을 소수 둘째 자리로 반올림한다.
- unresolved critical conflict는 해당 영역 factor=0, 전체 confidence 최대 0.49.
- freshness는 조회 TTL 안이면 1, 만료면 0.5; 정책 유효성 실패는 금융 영역 0. 과거 사건 자료는 사건이 오래됐다는 이유만으로 만료시키지 않는다.
- 모든 mock 실행은 최종 confidence=0.0, `confidence_basis="synthetic_data"`. 실연결 전 strong_buy_candidate가 나오지 않는 것은 의도된 동작이다.
- 영역별 점수/부족사유를 `data_quality`에 출력한다. API 실패·소득 미입력에 대해 사용자가 이유를 볼 수 있어야 한다.

## 15. AnalysisResult와 보고서 계약

최상위 필드:

```text
schema_version, analysis_id, property_slug, analyzed_at, as_of,
data_mode, simulation_only, profile_hash, rules_hash,
property, identity_status, verdict, price_analysis,
sale_history[], sale_history_analysis,
nearby_comparables[], comparable_analysis,
recent_new_supply_comparables[], new_supply_analysis,
alternatives[], alternatives_analysis, location_analysis,
strengths[], weaknesses[], user_fit, policy_finance, score,
evidence[], conflicts[], data_quality, missing_information[],
warnings[], report
```

요구사항 예시의 키를 유지한다. 배열 외의 추가 분석 필드에는 상태·검색범위·표본수를 둔다. 리스트가 비어 있는 이유를 `status`로 설명한다. `verdict.confidence`는 14.3의 값이다.

보고서는 LLM 없이 동일 JSON에서 생성한다. 섹션 순서:

1. 모의/실데이터 여부, 단지·주택형, 분석 기준일, 판정과 핵심 이유.
2. ‘살 수 있는가’: 분양가, 알려진 취득비용, 미확인 비용, 금융 검토 상태.
3. ‘왜 이 가격인가’: 사실 → 비교 → 해석 → 미확인 가설.
4. 분양이력 타임라인과 해석.
5. 네 그룹 기존거래 비교표, 최근 신규분양 비교표.
6. 대체재와 얻는 것/포기하는 것, 현재 구매 가능성 구분.
7. 사용자 10개 질문의 답과 SH 시간 선택권.
8. 점수의 보조적 의미·근거 부족·현장/자금계획에서 확인할 사항.
9. 출처 목록.

숫자는 JSON 계산결과를 포맷할 뿐 다시 계산하거나 창작하지 않는다. 금액은 원 단위 원본을 유지하고 사람이 읽는 부분만 억/만원으로 변환한다. ‘자료 없음’을 장황하게 반복하지 않되 중요한 결측은 생략하지 않는다. 나중에 LLM을 붙여도 구조화 JSON의 사실과 verdict는 수정할 수 없는 입력이다.

## 16. 함수 실행 순서와 오류 계약

공개 Python 진입점은 `async def analyze_property(property_input: PropertyInput | dict, *, deps=None) -> AnalysisResult`. 기본 deps는 설정으로 생성하며 테스트에서는 명시적으로 주입한다. 서비스 클래스를 만들더라도 이 함수를 유지한다.

```text
1 validate input; snapshot profile/rules; allocate id/as_of
2 resolve identity; collect basic property and notices
3 geocode when address is known
4 concurrently fetch independent transactions/supplies/places/routes
5 normalize facts; deduplicate evidence; record conflicts
6 compute costs/history/comparables/new_supply/alternatives/location/finance
7 compute user_fit and score; data_quality/confidence; verdict
8 render report; validate all evidence references
9 atomically save result; return AnalysisResult
```

독립 작업의 실패를 수집하고 남은 시간 내 부분 결과를 처리한다. 분석 엔진 내부는 네트워크를 호출하지 않는다. 의존성 없는 단계는 async 병렬화할 필요 없이 순수 함수로 실행한다.

전체 deadline에 도달하면 완료된 자료로 partial report를 생성한다. 초기 필수 설정/입력 오류 또는 저장 실패는 정상 성공으로 반환하지 않는다. 취소된 task와 HTTP client를 정리한다.

## 17. API와 파일 저장

| Endpoint | 요청 / 응답 | 오류 |
| --- | --- | --- |
| `GET /health` | `{status:"ok", mode, schema_version}`; 외부 API를 호출하지 않음 | startup 설정 오류는 서버 기동 실패 |
| `POST /analyze` | PropertyInput → 저장된 AnalysisResult, HTTP 200 | 422 입력 오류, 409 식별 모호, 500 내부/저장 오류 |
| `GET /profile` | 검증된 현재 프로필 JSON | 민감값은 로컬 응답에만, 로그 출력 금지 |
| `POST /profile/validate` | 프로필 객체 → `{valid:true, normalized_profile}` | 422 스키마/교차검증 오류; 저장 안 함 |
| `GET /reports/{property_slug}` | 해당 대상의 가장 최근 정상 저장 AnalysisResult | 404 미존재, 422 잘못된 slug |

외부 소스 전체 실패라도 입력으로 가능한 분석은 200이며 `data_quality`로 실패를 드러낸다. HTTP 200을 ‘분석 신뢰도 충분’의 의미로 사용하지 않는다.

에러 구조는 FastAPI 검증 오류 형식을 유지하고 업무 오류는 `{detail:{code,message,details}}`로 통일한다. 키·원문 프로필이 포함된 upstream exception을 그대로 반환하지 않는다.

`property_slug`: 읽기용 정규화 이름 prefix(최대 40자)+`-`+SHA-256 앞 16자. 해시 입력은 공식 ID+주택형 또는 미확정 이름+지역/주소+주택형이다. 가격은 포함하지 않아 같은 주택형 재분석을 묶는다. 식별 미확정→확정 시 slug가 달라질 수 있음을 문서화한다.

저장 경로는 `data/reports/{property_slug}/{UTC_timestamp}_{analysis_id}.json`. 파일 하나에 JSON과 report 문자열을 모두 저장한다. 같은 폴더 임시파일에 쓴 뒤 `os.replace`로 원자적 저장한다. UUID가 동시 실행 충돌을 막는다. 조회는 정상 파일의 analyzed_at 최신순으로 결정하며 깨진 파일은 경고 후 건너뛴다. 모두 깨졌으면 저장소 오류다.

slug는 서버 생성 형식만 허용하고 경로 구분자/`..`를 거부한다. resolve된 경로가 reports root 내부인지 확인한다. 분석마다 입력과 프로필은 메모리 snapshot으로 고정하고 결과에는 profile/rules hash를 남긴다. 전체 금융 프로필을 보고서에 복제하지 않는다.

## 18. 합성 fixture 설계

실존 단지에 가짜 거래이력이나 부정적 사실을 붙이지 않는다. 테스트는 `테스트 서울 소형 A`, `테스트 부천 B`, `테스트 구리 C`, `테스트 외곽 D` 등 합성 이름과 `fixture://` 출처를 사용한다. README의 실제 단지명 입력 예시에는 실제 데이터를 확보하기 전까지 수치 검증을 했다고 쓰지 않는다.

각 fixture는 대상, 공급 사건, 네 그룹 거래, 신규분양, 대체재, 위치정보, evidence를 포함한다. 모든 데이터에 `is_mock=true`를 붙인다. unknown name은 fixture의 다른 단지로 매핑하지 않고 missing을 반환한다.

| Case | 입력 조건 | 필수 검증 |
| --- | --- | --- |
| A | 서울 37.35㎡, 4.46억, 신축 | 면적 강한 타협으로 pass; 서울/신축 선호는 설명하되 면적 문제 상쇄 금지; SH 시간 선택권 설명 |
| B | 경기 부천 52㎡, 4.3억, 신축, 150세대 | 면적 80점, 예산 100점, 단지규모 50점; 150은 <150에 속하지 않음; 주소만 서울로 바꿔도 점수 동일 |
| C | 구리 38㎡, 6.7억, 신축, 3000세대, 확인된 역세권 | 단지규모 100점, 면적 10점, 예산 50점, pass; 가상 정책 규칙의 가격조건 실패와 실제 정책 미검증을 구분 |
| D | 남양주 외곽 59㎡, 5억, 신축 | 직장 null이면 통근 null; 별도 프로필/모의 경로 80분일 때 통근 10점, pass; 지역명만으로 장거리 추정 금지 |

모든 케이스의 기본 사용자 프로필은 직장 null이다. 긍정 판정과 통근 분기를 검증하는 테스트에서만 명시적으로 workplace와 완결 데이터를 주입한다. 실데이터 confidence 테스트는 공식 출처처럼 위조한 fixture가 아니라 테스트 내부의 source-quality 입력을 대상으로 하며 서비스 mock 플래그는 유지한다.

## 19. 구현 작업 순서와 완료 조건

### Phase 1 — 실행 골격과 데이터 계약

**P1.1 프로젝트/설정**: pyproject, 패키지, settings, app factory, health, `.gitignore`, `.env.example`. Git 제외는 `.env`, cache, reports, 로컬 금융 프로필 오버라이드. 기본 요구사항 프로필에는 비밀정보가 없으므로 예제값을 포함할 수 있다.

완료: editable 설치 후 서버 health=200, config 오류가 startup에서 검출된다.

**P1.2 스키마/설정파일**: 4~5절의 모델, 사용자 YAML, 미검증 finance YAML, analysis rules를 작성한다. 모델 간 순환 import를 피하도록 common → property/profile/market → analysis 순으로 의존한다.

완료: 원문 입력 예제 두 종류와 프로필을 파싱하고 잘못된 가격/면적/프로필은 거부한다.

**P1.3 mock/storage**: source Protocol, fixture A~D, registry, cache, report store를 작성한다.

완료: 외부 네트워크 없이 mock 조회 및 원자적 저장/조회가 동작하고 근거가 보존된다.

### Phase 2 — 분석과 종단 실행 (필수 완성)

**P2.1 식별·정규화·비용·이력**: identity, normalize, costs, sale_history. 중복/충돌/결측 모델을 우선 확립한다.

**P2.2 비교와 대안**: comparables, new_supply, alternatives, location. 같은 면적 가격판정과 큰 면적 기회비용을 분리하고 검색 범위를 전달한다.

**P2.3 금융·적합성·점수·판정**: finance → user_fit → scoring → confidence → verdict 순서로 작성한다. 경계값과 promotion 차단 조건을 테스트한다.

**P2.4 report·서비스·API**: renderer, analyze 함수, routes, 저장을 연결한다. 모든 10개 질문과 근거 참조를 검증한다.

**P2.5 통합 검증/문서**: 테스트, README, API 예제, 키 필요 목록, 구현/mock/미구현 구분을 작성한다.

완료: A~D 종단 분석, report 저장/조회, 외부 실패 부분분석, 모의 표시, 정책 미검증 상태, 모든 필수 테스트가 통과한다. ‘실제 투자분석 가능’이라는 문구는 실연결 전 사용하지 않는다.

### Phase 3 — 청약Home / LH 선택 연결

1. 공식 공공데이터 제공 페이지와 이용기관 문서에서 실제 서비스명, endpoint, 인증 방식, 이용신청 필요 여부, pagination, 지원 공고 범위를 확인한다.
2. `docs/data_sources.md`에 검증일/공식 문서 URL/지원 필드/제한/환경변수명을 기록한다. 이 계획만 보고 endpoint를 추측하지 않는다.
3. 키 확보 여부와 관계없이 공개 명세가 확인되면 sanitized 응답 contract fixture로 parser를 구현할 수 있다. 실제 live 검증은 키가 있을 때만 수행한다.
4. `applyhome.py`, `lh.py`만 실제 연결하고 나머지는 live unavailable 유지한다. LH 결과에서 rental_only를 제외하되 분양 유형과 구분을 보존한다.
5. 실제 API에 과거 계약결과/혜택 정보가 없으면 그 필드를 missing으로 반환한다.
6. 한 단지 식별→공고/주택형→기본 가격 정규화 smoke test를 수행하고 응답의 원문 URL을 추적한다. 테스트 산출물에 키를 저장하지 않는다.

키/공식 명세 미확보 시 연결 완료로 표시하지 않고 Phase 1~2 완료와 별개로 남은 조건을 적는다. 실제 청약/LH 연결만으로 주변 시장가 분석까지 실데이터가 되지는 않는다.

### Phase 4~6 — 후속 범위

- P4: 국토부 실거래 API, 계약취소 반영, 법정동/월별 pagination, KAPT·좌표 연결, 실제 comparable 검증.
- P5: 공식 공고 아카이브와 검증 가능한 웹자료의 분양이력, 최근 3~5년 신규분양, 현재 공급 가능 대체재. 자동 확정이 어려운 사실은 수동 검증을 지원하는 명시적 자료 입력으로 보완 가능하게 설계하되 별도 관리 UI는 만들지 않는다.
- P6: 지도·시설·실제 대중교통 경로. 제공자가 door-to-door를 지원하는지 먼저 검증한다.

## 20. 검증 계획

테스트는 기본적으로 네트워크를 차단하고 임시 디렉터리, 고정 시계, 합성 데이터로 실행한다. live smoke는 opt-in으로 분리한다.

필수 단위 검증:

- 면적 39.99/40/49.99/50/58.99/59, 가격 6억/6억+1/7억/7억+1, 세대수 149/150/299/300/499/500, 통근 40/60/61분 경계.
- 결측 면적·가격·세대수·직장이 0이나 정상값으로 바뀌지 않음.
- 확장비 unknown과 명시적 0의 차이, 비용 합산, 대출 미확정 시 자기자금 null.
- 거래 취소/중복/조회기간/최소 표본/동일 생활권/더 큰 면적 그룹 분리.
- 같은 공고 재게시를 재공급 횟수로 중복 계산하지 않음; 반복공급만으로 avoid 금지.
- 정책 미검증/만료/필수 입력 누락/확정 불충족/조건부/충족 상태 전부 검증.
- 점수 부족 coverage, 높은 점수지만 작은 면적·긴 통근·핵심 결측 때문에 승격 차단.
- avoid 우선순위와 근거 없는 위험 추론 금지; 온전한 입력으로 consider/strong 조건을 각각 검증.
- 모든 finding/evidence 참조가 존재하고 mock confidence=0.
- 과거 분양/실거래 대안은 현재 판매중으로 표시되지 않음.
- 보고서 Q1~Q10 존재, JSON과 보고서 금액 일치, mock 표시 유지.

필수 통합 검증:

- A~D에 대해 `/analyze` → JSON/report → `/reports/{slug}`가 동일 analysis_id를 반환.
- `/profile`, validate 정상/오류, validate가 파일을 수정하지 않음.
- 동명이단지 409, 알 수 없는 단지는 입력 기반 partial, malformed 입력 422, 없는 report 404.
- 소스 timeout/429/키 없음/잘못된 응답/부분 pagination을 재현해 오류와 범위가 보존됨.
- 캐시 hit/expiry/키 미포함, 파일 손상, 저장 권한 오류, 동시 저장, 경로 탈출 차단.
- live 모드에서 mock 결과가 섞이지 않음.

예상 실행 명령(구현 후 README에 실제 검증한 명령으로 확정):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
python -m ruff check .
HOME_AGENT_SOURCE_MODE=mock python -m uvicorn home_agent.main:app --host 127.0.0.1 --port 8000
```

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"name":"테스트 서울 소형 A","region":"서울 구로구","unit_type":"37A","exclusive_area_m2":37.35,"price_krw":446000000}'
```

## 21. 구현자가 임의로 확정하면 안 되는 사항

- 현재 금융정책의 가격상한·소득/자산기준·금리·대출액: 공식 규정과 기준일을 확인하기 전까지 unknown.
- 사용자 실제 소득/자산/대출/직장: nullable 유지. 이를 기다리느라 mock MVP 구현을 멈추지 않는다.
- 청약Home/LH/국토부/지도 제공자의 구체 endpoint와 key 명칭: 공식 명세 검증 후 확정한다.
- 가격 프리미엄의 실제 원인, 완판 여부, 구조적 위험, 현재 매물 존재: 근거 없으면 hypothesis 또는 unknown.
- 미래 집값·지역 인구변화 효과·실제 매도 가능성: 본 MVP의 예측 출력에 포함하지 않는다. 확인된 지역자료를 향후 설명 근거로 추가할 수 있다.

그 외 파일 분할·내부 함수명 같은 되돌릴 수 있는 구현 선택은 본 계약을 유지하면서 구현자가 결정한다. 이 계획은 사소한 변경마다 재승인을 요구하지 않는다.

## 22. 최종 인수 체크리스트

- [ ] 새 환경에서 README 명령으로 설치·서버·테스트 실행 가능.
- [ ] 원문 요구사항의 A~H 분석 항목과 10개 질문이 JSON/report에 모두 존재.
- [ ] Phase 1~2 전체 동작, LLM/API key/DB 없이 실행 가능.
- [ ] mock·결측·충돌·조회 범위·기준일이 결과에 명시됨.
- [ ] 비용 총액과 필요 자기자금을 혼동하지 않음.
- [ ] 점수와 최종 판단이 분리되고 낮은 긴급성·면적·통근 타협이 반영됨.
- [ ] 공식 사실을 LLM이나 단지명/지역명에서 추측하지 않음.
- [ ] 네 케이스와 오류/경계 테스트 통과.
- [ ] API key·개인 금융정보·캐시/보고서가 Git에 유출되지 않음.
- [ ] 구현 완료 보고에 현재 기능 / mock 부분 / 실연결에 필요한 키·신청 / 검증된 실행 명령 / 다음 우선순위를 구분해 전달.
