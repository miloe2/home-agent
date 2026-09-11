requirement.md를 읽고 해당 요구사항을 구현하기 위한 상세한 plan.md를 작성해줘.

너는 수석 소프트웨어 아키텍트 역할이다.

실제 구현은 하지 말고 설계와 구현 계획만 작성해.
저비용 구현 모델이 plan.md만 읽고 그대로 구현할 수 있을 정도로 구체적으로 작성해.

requirement.md 마지막의 "비싼 모델에게 요청할 작업" 요구사항을 반드시 준수해.

개인용 "내집마련 분석 백엔드"를 만들어줘.

중요:
이 프로젝트는 아직 서비스 출시용이 아니다.
나 한 명이 실제 아파트를 고르기 위해 사용하는 개인용 분석도구다.

현재 단계에서는:
- 프론트엔드 만들지 말 것
- Slack/Telegram 알림 만들지 말 것
- DB 만들지 말 것
- 로그인/회원가입 만들지 말 것
- 사용자 관리 만들지 말 것

핵심 목표는 하나다.

"특정 분양/청약 아파트를 입력하면,
내 상황에 비추어 이 집을 실제로 살 가치가 있는지
근거를 수집해서 분석해주는 백엔드"

단순히 점수만 출력하면 안 된다.

내가 원하는 결과는 다음과 같은 분석이다.

예:
"서울 신축이고 4.4억이라 처음에는 싸 보이지만,
전용 37㎡라 장기 실거주에는 작은 편이다.
이 단지는 최초 분양 이후 잔여물량이 반복되어
시장이 이 가격을 강한 저가매력으로 평가하지 않았을 가능성이 있다.
반경/인근 생활권의 구축 59㎡는 대략 X~Y억이고,
비슷한 가격대의 다른 신규분양에는 50㎡ 이상도 존재한다.
따라서 SH에서 장기간 더 거주할 수 있는 사용자라면
서울 주소를 얻기 위해 면적을 이 정도까지 타협할 필요는 낮다."

이런 식으로
"왜 사야 하는가 / 왜 사지 말아야 하는가"
를 설명해야 한다.

────────────────
1. 내 사용자 프로필
────────────────

사용자 프로필은 YAML 파일로 관리한다.

config/user_profile.yaml

현재 내 상황:

household:
  marital_status: married
  newlywed: true
  first_time_homebuyer: true
  homeowner: false
  current_housing: SH public rental
  remaining_stable_housing_years: 10

housing_strategy:
  urgency: very_low
  reason:
    - 현재 SH 주택에서 약 10년 더 안정적으로 거주 가능
    - 따라서 FOMO 때문에 아무 집이나 살 필요 없음
    - 좋은 기회가 아니면 기다릴 수 있음

purchase_goal:
  purpose:
    - long_term_primary_residence
    - asset_preservation
  rental_property: false
  investment_only_property: false

property_preferences:
  property_type:
    include:
      - apartment
    exclude:
      - officetel
      - villa
      - regional_housing_cooperative
      - rental_only

  location:
    include:
      - Seoul
      - Gyeonggi
    preference:
      Seoul: preferred_but_not_required
      Gyeonggi: acceptable

  philosophy:
    - 서울 주소 자체보다 실제 생활 편의와 출퇴근 시간을 중요하게 봄
    - 돈이 충분하면 서울을 선호하지만 서울이라는 이유만으로 큰 타협은 하지 않음
    - 경기라도 직장이 가깝거나 서울 접근성이 좋으면 충분히 고려
    - 구리 같은 서울 인접 경기지역에 긍정적
    - 수도권 외곽에서 서울까지 장시간 통근하는 것은 싫음

  commute:
    metric: door_to_door
    ideal_one_way_minutes: 40
    acceptable_one_way_minutes: 60
    strongly_penalize_over_minutes: 60
    reason:
      - 왕복 출퇴근 2시간 이상이면 삶의 질이 크게 떨어진다고 생각함
    # 직장 주소는 아직 미정이므로 nullable 처리할 것
    workplace_address: null

  area:
    ideal_exclusive_m2: 59
    acceptable_min_exclusive_m2: 50
    strong_penalty_below_m2: 40
    philosophy:
      - 부부 장기 실거주 기준
      - 37~38㎡는 서울/신축이라도 큰 타협으로 평가
      - 향후 가족구성 변화 가능성도 고려
      - 50~59㎡ 이상을 선호

  complex:
    prefer_large_complex: true
    ideal_households_min: 500
    small_complex_penalty_below: 300
    very_small_complex_penalty_below: 150

  age:
    prefer_new_build: true
    new_build_bonus: true
    old_build_allowed: true
    # 신축이라는 이유만으로 과도한 프리미엄은 지불하고 싶지 않음

budget:
  preferred_max_price_krw: 600000000
  stretch_max_price_krw: 700000000

finance:
  interested_in_policy_mortgage: true
  programs_of_interest:
    - didimdol
    - bogeumjari
    - first_time_homebuyer
    - newlywed
  philosophy:
    - 6억원 이하 등 정책대출에 유리한 가격구간을 중요하게 평가
    - 단, 대출이 나온다는 이유만으로 좋지 않은 집을 추천하지 말 것
    - 실제 대출 승인 가능액은 사용자 소득/자산 입력 전에는 확정하지 말 것

decision_philosophy:
  - "살 수 있다"와 "살 만하다"를 구분할 것
  - 현재 10년의 시간 선택권이 있기 때문에 애매한 집은 보류가 기본값
  - 싸 보이는 집에는 왜 싼지 반드시 이유를 찾을 것
  - 비싸 보이는 집에는 시장이 왜 프리미엄을 주는지도 찾을 것
  - 서울이라는 이유만으로 소형면적/나쁜상품성을 정당화하지 말 것
  - 경기라는 이유만으로 저평가하지 말 것
  - 장기 실거주성과 향후 매도 수요를 동시에 볼 것
  - 인구감소 시대에는 지역 전체보다 해당 입지/단지의 선택 이유가 지속되는지를 중요하게 평가

────────────────
2. 프로젝트의 핵심 기능
────────────────

첫 MVP에서는 아래 함수가 핵심이다.

analyze_property(property_input)

입력 예:

{
  "name": "개봉 루브루",
  "region": "서울 구로구",
  "unit_type": "37A",
  "exclusive_area_m2": 37.35,
  "price_krw": 446000000
}

또는 최소:

{
  "name": "구리역 하이니티 리버파크",
  "unit_type": "38",
  "price_krw": 670000000
}

입력정보가 부족하면
외부 데이터 source adapter를 이용해 보완한다.

결과는 반드시 구조화된 JSON + 사람이 읽을 수 있는 report를 반환한다.

────────────────
3. 분석 항목
────────────────

A. 기본 상품 분석

확인:
- 정확한 단지명
- 주소
- 건설사
- 총 세대수
- 동수
- 입주 예정일
- 신축/구축
- 전용면적
- 공급면적
- 방/욕실 구조 가능하면 확인
- 분양가
- 발코니 확장비
- 필수 옵션
- 실제 취득 예상가격

중요:
"분양가 4.4억"만 보지 말고
실제 필요한 총 현금가격을 계산 가능한 구조로 만든다.

B. 분양 이력 분석

매우 중요하다.

해당 단지가 과거에:
- 최초 분양일
- 최초 분양가
- 청약 경쟁률
- 계약 결과
- 미계약 여부
- 무순위
- 임의공급
- 선착순
- N차 재공급
- 가격 할인 여부
- 혜택 추가 여부

가 있었는지 수집한다.

예:

"2024년 최초 분양 → 미계약 발생
→ 2025년 무순위
→ 2026년 4차 임의공급"

같은 history timeline을 만들어라.

그리고 단순 사실만 보여주지 말고 해석한다.

예:
"몇 년간 같은 가격에 잔여세대가 반복되었다면
시장이 해당 가격을 특별한 저가로 평가하지 않았다는 신호일 수 있음"

단,
미분양 = 무조건 나쁜 집이라고 단정하지 말 것.
분양 당시 시장 상황, 금리, 입주 리스크 등도 고려한다.

C. 주변 기존 아파트 가격 분석

국토부 실거래가 API 등을 사용해
해당 단지 주변의 실제 아파트 거래를 조사한다.

비교대상(comparable)은 단순 거리순이 아니라:

- 같은 생활권
- 같은 역세권
- 비슷한 전용면적
- 비슷한 세대수
- 비슷한 연식
- 신축/준신축/구축

으로 분류한다.

최소:
1. 같은 면적대
2. 한 단계 큰 면적 (예: 신규 37㎡라면 주변 49/59㎡)
3. 신축 또는 준신축
4. 대표 구축

을 비교한다.

예:

신규분양:
37㎡ 4.46억

주변:
2010년식 59㎡ 최근 실거래 4.8~5.2억
2021년식 59㎡ 최근 실거래 5.7~6.1억

이 경우:
"서울 신축 프리미엄을 얻는 대신 면적을 크게 포기하는 가격구조"
라는 식으로 해석한다.

D. 과거/현재 인근 신규분양 비교

이 기능이 매우 중요하다.

해당 지역 및 인접지역에서 최근 3~5년간 분양한 단지를 찾는다.

비교:
- 단지명
- 위치
- 분양연도
- 면적
- 당시 분양가
- 현재 실거래가
- 세대수
- 역거리
- 완판/미분양 이력

예:
"이 단지 52㎡ 4.3억인데,
1년 전 인근 A단지 59㎡가 4.5억에 분양됐다"
같은 정보를 찾아야 한다.

이를 통해:
- 현재 분양가가 진짜 싼지
- 신축 프리미엄이 과한지
- 해당 생활권의 가격이 어떻게 변했는지

를 판단한다.

E. 대체재 분석

현재 물건만 보지 말고,
같은 예산으로 무엇을 살 수 있는지 비교한다.

예:
4.5억원의 서울 37㎡ 신축

vs

4.3억원 부천 52㎡ 신축
5억원 남양주 59㎡ 신축
4.8억원 서울 구축 59㎡

이런 식이다.

중요한 질문:

"이 집을 사면 무엇을 얻고,
대신 무엇을 포기하는가?"

반드시 답해야 한다.

F. 입지 분석

가능하면 아래 정보 수집 interface를 만든다.

- 가장 가까운 지하철역
- 도보거리
- 주요 업무지구 접근성
- 서울 중심 접근성
- 강남 접근성
- 주요 교통호재
- 상권
- 병원
- 학교
- 대형마트
- 생활 인프라

단,
GTX 등 미래 교통망은:
계획 / 착공 / 공사중 / 개통확정
상태를 구분한다.

"GTX 예정이므로 무조건 호재"
같은 판단 금지.

G. 정책대출 적합성

정책은 별도 config 파일로 관리한다.

config/finance_rules.yaml

현재 날짜 기준 공식 금융기관 자료를 source of truth로 사용한다.

판정은:
- likely eligible
- possibly eligible
- not eligible
- insufficient_information

중 하나로 한다.

예:
주택가격 기준 충족
면적 기준 충족
무주택/신혼/생애최초 조건 검토가능

하지만
사용자의 정확한 세전소득, 신고 사업소득, 순자산이 없으면
"최종 가능"이라고 말하지 않는다.

H. 사용자 적합성

단순 scoring 외에 반드시 qualitative reasoning을 만든다.

아래 질문에 답한다.

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

────────────────
4. 결과 포맷
────────────────

분석 결과 예:

{
  "property": {...},

  "verdict": {
    "status": "watch",
    "confidence": 0.82,
    "summary": "가격은 매력적이나 면적 타협이 커서 현재 사용자에게는 보류"
  },

  "price_analysis": {
    "asking_price": 446000000,
    "effective_price": 455000000,
    "assessment": "fair_to_expensive",
    "reasoning": [...]
  },

  "sale_history": [...],

  "nearby_comparables": [...],

  "recent_new_supply_comparables": [...],

  "alternatives": [...],

  "strengths": [...],
  "weaknesses": [...],

  "user_fit": {
    "good": [...],
    "bad": [...]
  },

  "policy_finance": {...},

  "score": {
    "total": 68,
    "components": [...]
  },

  "report": "..."
}

score는 보조정보일 뿐이다.

절대로:
"82점입니다. 좋은 집입니다."
로 끝내지 마라.

────────────────
5. Verdict 체계
────────────────

최종 판단은 점수보다 아래 상태를 더 중요하게 사용한다.

strong_buy_candidate
- 현재 사용자 조건에서 매우 보기 드문 좋은 기회
- 실제 현장/자금계획까지 검토 가치 큼

consider
- 충분히 검토할 가치 있음

watch
- 장점은 있지만 지금 당장 살 이유는 부족

pass
- 현재 사용자에게 타협이 큼

avoid
- 구조적 리스크가 큰 후보

SH에서 장기간 거주할 수 있기 때문에
기본적으로 애매하면 watch/pass를 선택한다.

FOMO를 부추기지 않는다.

────────────────
6. 데이터 소스 구조
────────────────

각 외부 데이터는 adapter interface로 분리한다.

sources/
  applyhome.py
  lh.py
  molit_transactions.py
  kapt.py
  geocoding.py
  transit.py
  web_search.py

현재 API key가 없으면 mock adapter를 만든다.

공공 API를 우선한다.

공식 API로 얻을 수 없는:
- 과거 분양 뉴스
- 미분양 경과
- 분양가 평가
- 주변 개발 진행상황

등은 web_search adapter로 보완 가능하게 설계한다.

각 데이터에는 source_url, fetched_at, source_type을 저장한다.

분석 결과가 어떤 근거에서 나왔는지 추적 가능해야 한다.

────────────────
7. 저장소
────────────────

DB는 만들지 않는다.

현재는:

data/
  cache/
  fixtures/
  reports/

를 사용한다.

HTTP response cache를 JSON으로 저장해서
개발 중 공공 API를 계속 호출하지 않도록 한다.

property 분석 결과 역시 JSON 파일로 저장할 수 있게 한다.

향후 DB로 교체하기 쉽도록 repository interface는 필요하면 만들되,
실제 DB dependency는 추가하지 않는다.

────────────────
8. API
────────────────

FastAPI endpoint:

GET /health

POST /analyze

예:
POST /analyze
{
  "name": "부천역 에피트 어바닉",
  "unit_type": "52",
  "price_krw": 436000000
}

GET /profile

POST /profile/validate

GET /reports/{property_slug}

처음에는 이 정도만 만든다.

────────────────
9. LLM 사용
────────────────

LLM은 필수 dependency로 만들지 않는다.

공식 데이터:
- 가격
- 면적
- 청약조건
- 경쟁률
- 실거래
- 세대수

등은 절대로 LLM이 추측하지 않는다.

rule engine + data analysis가 먼저다.

LLM을 나중에 붙일 경우:
structured analysis JSON을 입력받아
사람에게 읽기 좋은 최종 report를 만드는 역할만 한다.

즉:

Data → Rules → Analysis → LLM explanation

순서다.

LLM → 사실 생성

구조는 금지한다.

────────────────
10. 구현 우선순위
────────────────

Phase 1

- Python project 생성
- FastAPI
- user_profile.yaml
- finance_rules.yaml
- PropertyInput / AnalysisResult schema
- mock source adapters

Phase 2

- analysis engine
- scoring engine
- verdict engine
- mock comparable 분석
- report 생성

Phase 3

- 실제 청약Home API 연결
- LH API 연결

Phase 4

- 국토부 실거래가 API 연결
- 주변 comparable 선정 알고리즘

Phase 5

- 과거 분양이력 및 최근 신규분양 비교

Phase 6

- 지도/통근 API

지금은 Phase 1~2를 완전히 동작하게 만들고,
가능하면 Phase 3의 실제 API 연결까지 진행해라.

────────────────
11. 테스트
────────────────

반드시 아래 테스트 케이스를 만든다.

Case A:
서울 37㎡ / 4.4억 / 신축
→ 가격과 서울 입지는 장점
→ 면적은 강한 감점
→ SH 10년 사용자에게 watch/pass 가능

Case B:
경기 부천 52㎡ / 4.3억 / 신축 / 150세대
→ 면적/가격은 장점
→ 소규모 단지는 감점
→ 서울이 아니라는 이유만으로 낮게 평가하면 안 됨

Case C:
구리 38㎡ / 6.7억 / 3000세대 / 역세권
→ 입지/대단지 매우 좋음
→ 면적/가격/정책대출 측면 감점

Case D:
남양주 외곽 59㎡ / 5억 / 신축
→ 상품 자체는 좋음
→ 서울/직장 통근이 길다면 강하게 감점

────────────────
12. 중요한 제품 철학
────────────────

이 도구는 청약 공고 알리미가 아니다.

"나에게 좋은 집을 찾아주는 구매 의사결정 엔진"이다.

사용자가 가장 궁금한 질문은:

"신청할 수 있어?"
가 아니라

"그래서 이걸 내가 사는 게 좋은 선택이야?"

이다.

가격표만 분석하지 말고
"왜 이 가격인지" 설명하는 것을 가장 중요하게 구현해라.

먼저 전체 아키텍처를 간단히 설명한 뒤

완료 후:
1. 현재 구현된 기능
2. mock인 부분
3. 실제 API 연결에 필요한 key
4. 실행 명령
5. 다음 개발 우선순위
를 정리해라.

