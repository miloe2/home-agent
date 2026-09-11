지금까지 실제 LH 공고 5개를 돌려본 결과를 기준으로 분석 파이프라인을 점검하고 수정해줘.

중요:
단순히 Gemini prompt만 수정하지 말고,
현재 구현에서 아래 문제가 어느 계층에서 발생하는지 먼저 추적한 뒤 수정해줘.

우선순위는:

1. source/enrichment 데이터 누락 수정
2. comparable 선정 로직 수정
3. verdict 로직 수정
4. 마지막으로 Gemini narrative prompt 수정

잘못된 입력을 prompt로 덮어쓰면 안 됨.

# 1. 프로젝트의 최상위 목적 재확인

이 도구의 핵심 질문은:

"이 청약에 신청할 수 있는가?"

가 아니라

"현재 안정적인 공공임대에서 약 10년 더 거주할 수 있는 내가,
그 선택권을 포기하고 지금 이 집을 매수할 가치가 있는가?"

이다.

따라서 SH 10년 거주 가능성은 모든 매물을 자동 watch로 만드는 veto가 아니다.

SH 10년은 매수 threshold를 높이는 요소다.

좋은 기회라면 consider 또는 strong_buy_candidate가 실제로 나올 수 있어야 하고,
애매한 후보라면 watch,
핵심 조건을 크게 위반하면 pass가 나와야 한다.

# 2. 지금까지 실제 검증에서 발견된 문제

실제 테스트:

* 양주회천 A-26
* 의정부우정 A2
* 인천계양 A6
* 남양주왕숙2 A-3
* 성남복정2 A1

를 실행했다.

## 문제 A. comparable benchmark와 narrative가 충돌함

예:

양주회천 59㎡

* 분양가 약 3.57억
* benchmark 약 1.705억
* ratio 2.09배 → expensive

그런데 narrative에 나온 대표 비교단지는:

* 덕정역서희스타힐스에듀포레뷰 약 3.175억
* 덕계역금강펜테리움센트럴파크 약 3.345억
* 더 넓은 양주옥정유림노르웨이숲 약 3.8억

등이다.

사용자 입장에서는:

"주변보다 2배 비싸다는데 왜 대표 비교단지는 대상 가격과 비슷하지?"

라는 모순이 생긴다.

남양주왕숙2도 비슷한 현상이 있다.

예:
74㎡ 분양가 약 6.46억
benchmark 약 4.055억 → expensive 1.59배

그런데 narrative에는:

* 다산반도유보라메이플타운 약 8.5억
* e편한세상 다산 약 8.98억

등이 등장한다.

즉 산술 계산 자체보다 comparable universe가 너무 넓거나
생활권/연식/상품성이 다른 단지까지 median-of-medians에 포함되는 문제가 의심된다.

## 수정 요구

PLAN.md의

"단지별 median의 median"

방식 자체는 유지해도 된다.

문제는 그 전에 comparable candidate를 더 엄격하게 제한해야 한다.

최소한 primary price comparable은:

* 동일 생활권 우선
* 인접 생활권은 secondary
* 유사 전용면적
* 아파트
* 최근 거래
* 최소 거래건수 조건
* 신축 / 준신축 / 구축 구분
* 너무 오래되거나 상품성이 현격히 다른 단지는 primary benchmark에서 제외

하도록 개선해줘.

가능하면 comparable마다 선정 이유를 남겨라.

예:

{
"complex_name": "...",
"distance_km": ...,
"exclusive_area_m2": ...,
"build_year": ...,
"transaction_count": ...,
"median_price": ...,
"comparable_tier": "primary",
"selection_reason": [
"same_living_area",
"similar_area"
]
}

그리고 benchmark를 만들 때 실제 어떤 단지들이 포함됐는지 debug 가능한 구조로 남겨라.

# 3. 인천계양 A6 지역 매칭 문제 확인 및 수정

인천계양 A6 테스트에서 primary comparable에:

* 마곡
* 등촌
* 우장산
* 강서구 아파트

등이 다수 들어갔다.

이 데이터 자체가 필요 없는 것은 아니다.

하지만 이것들을 인천계양 A6의 "현지 적정가격 benchmark"에 직접 넣는 것은 문제가 있다.

역할을 분리해라.

## Primary price comparables

질문:

"계양 A6 분양가가 해당 생활권 및 인접 생활권에서 비싼가?"

비교군:

* 계양 생활권
* 인접 부천 생활권
* 유사 면적
* 유사 상품성

## Alternative / substitution comparables

질문:

"같은 돈 또는 조금 더 주면 서울 강서권에서는 무엇을 살 수 있는가?"

여기에는:

* 마곡
* 등촌
* 우장산
* 강서권

등을 사용할 수 있다.

즉:

price_comparables

와

alternatives

를 분리해서 사용해라.

서울 강서 시세가 높다는 이유만으로
인천계양 분양가를 cheap으로 판정하면 안 된다.

# 4. 세대수 / 입주예정일 enrichment 누락 수정

5개 테스트 모두 Gemini narrative에서 반복적으로:

* 세대수 확인불가
* 연식 확인불가
* 입주예정일 확인불가

비슷한 문구가 등장했다.

그런데 LH 공고에는 실제로 확인 가능한 데이터가 존재한다.

예:

* 양주회천 A-26: 세대수/입주예정일 존재
* 의정부우정 A2: 세대수/입주예정일 존재
* 인천계양 A6: 세대수/입주예정일 존재

따라서 Gemini가 추측할 문제가 아니라
source → structured analysis JSON 사이에서 데이터가 누락되는지 확인해야 한다.

신규 분양의 경우 "연식 확인불가"라는 표현도 적절하지 않다.

가능하면 구조를:

new_build: true
move_in_date: ...
total_households: ...

처럼 명시해라.

기존 아파트처럼 age_years를 요구하지 말고,
신규분양은 new_build / expected_move_in_date로 평가해라.

# 5. 리포트에서 불필요한 "확인불가" 항목 제거

현재 Gemini가 거의 모든 타입에서:

* 취득세
* 등기/법무비
* 확장비
* 필수 옵션비
* 세대수
* 연식
* 통근

등을 줄줄이 "확인불가"라고 나열한다.

개인용 MVP에서 너무 과하다.

리포트 본문에서 중요한 미확인 항목은 일단 다음만 남긴다.

* 세대수
* 입주예정일
* 통근

단,
세대수와 입주예정일은 원칙적으로 source에서 확보하도록 먼저 수정한다.

즉 실제로 자주 unknown으로 남을 항목은 통근일 가능성이 높다.

취득세, 등기비, 법무비, 확장비, 필수 옵션비 등은
verdict를 바꿀 정도로 중요한 특이사항이 있는 경우가 아니면
최종 narrative에서 일일이 나열하지 마라.

필요하면 structured JSON의 unknown_fields에는 남겨도 되지만
사용자용 report에서는 숨겨라.

# 6. 통근 모델 변경

기존 requirement에서는 workplace_address가 nullable이었다.

현재 사용자 직장은 아직 특정 회사 주소 하나로 확정하지 않는다.

사용자는 IT 개발자이고,
향후 근무 가능성이 높은 주요 업무지구를 기준으로
"장기적인 통근 유연성"을 평가하고 싶다.

기본 job center를 아래처럼 설정해라.

* 성수
* 강남
* 가산/구로디지털단지
* 성남/판교
* 문정

가능하면 config/user_profile.yaml에 다음과 유사한 구조를 추가해라.

commute:
mode: multi_job_centers

job_centers:
- name: seongsu
label: "성수"
weight: 0.9

```
- name: gangnam
  label: "강남"
  weight: 1.0

- name: gvalley
  label: "가산/구로디지털단지"
  weight: 0.8

- name: pangyo
  label: "성남/판교"
  weight: 1.0

- name: munjeong
  label: "문정"
  weight: 0.7
```

metric: door_to_door
ideal_one_way_minutes: 40
acceptable_one_way_minutes: 60
strongly_penalize_over_minutes: 60

weight 값은 필요하면 현재 scoring 구조에 맞게 조정해도 된다.

단순히 5곳의 평균 통근시간만 내지 마라.

예:

성수       52분
강남       43분
가/구디    71분
성남/판교  39분
문정       46분

이라면:

* 40분 이내: 1곳
* 60분 이내: 총 4곳
* 60분 초과: 1곳

처럼 distribution을 봐야 한다.

예시 qualitative 결과:

"강남·판교·문정 등 주요 IT 업무지구는 60분 이내 접근 가능하지만 가산/구디 접근성은 떨어진다. 향후 이직 가능성을 고려한 통근 유연성은 전반적으로 양호하다."

현재 실제 transit API가 없다면
임의로 시간을 생성하지 말고:

commute.status = "not_evaluated"

로 두되,
향후 multi_job_center 평가가 가능하도록 schema/interface를 먼저 정리해라.

# 7. unknown 처리 방식 수정

현재 엔진이 다음과 같이 작동하는지 확인해라.

좋은 조건
+
일부 정보 unknown
→ watch

이 구조가 너무 강하면 모든 후보가 watch로 고정된다.

unknown과 negative는 구분해야 한다.

예:

* price good
* area good
* budget good
* complex size good
* commute unknown

이라면 반드시 watch가 되어야 하는 것은 아니다.

필요하면:

verdict: consider
confidence: 0.45

blocking_checks:

* commute

처럼 표현할 수 있어야 한다.

즉:

unknown → confidence 감소

가 기본이고,

known negative → verdict 하락

으로 설계해라.

단, 통근처럼 사용자의 핵심 조건인 정보가 없을 경우
strong_buy_candidate까지 올리는 것은 제한할 수 있다.

# 8. verdict 상승 조건 점검

현재 실제 테스트 결과는 거의:

* watch
* pass

두 종류로만 수렴하고 있다.

나쁜 후보를 거르는 기능은 잘 작동하는 편이다.

하지만 좋은 후보를 찾아내는 기능은 아직 검증되지 않았다.

특히 인천계양 A6의:

69.82㎡ / 약 5.96억

같은 후보는 중요하다.

사용자 기준:

* ideal area 59㎡ 이상
* preferred max 6억
* 신축
* 중대형 단지
* 수도권

조건을 상당수 만족한다.

이런 후보도 정보가 일부 없다는 이유만으로 자동 watch가 된다면
시스템이 지나치게 보수적일 수 있다.

verdict semantics를 명확히 점검해라.

strong_buy_candidate:
현재의 10년 임대 선택권을 포기할 만큼
가격·입지·상품성에서 드문 수준의 우위가 확인됨.

consider:
현재 임대를 유지하는 것과 비교해도
실제 매수 검토 단계로 넘어갈 가치가 있음.
핵심 하드 조건을 충족하고 명확한 장점이 있음.

watch:
괜찮은 집이지만
현재 10년 임대 선택권을 포기할 정도의 우위는 아직 부족하거나
핵심 확인사항이 남음.

pass:
예산, 면적, 통근 등 핵심 조건을 크게 위반하거나
사용자가 감수해야 할 타협이 큼.

avoid:
가격과 무관하게 구조적 리스크가 큼.

# 9. 현재 5개 테스트에서 기대하는 방향

정답을 강제하는 것은 아니지만
수정 후 sanity check 기준으로 사용해라.

양주회천 A-26 59㎡

* 예상: watch ~ consider
* 가격 자체가 주변보다 2배 비싸다는 설명은 재검증 필요
* 실제 핵심 리스크는 서울/주요 업무지구 통근 가능성이 될 가능성이 큼

의정부우정 A2 59㎡

* 예상: watch ~ consider
* 가격/면적 조건은 상당히 무난
* 통근과 주변 신축/구축 대비 가격경쟁력이 중요

인천계양 A6 59㎡

* 예상: consider 가능
* 현재 서울 강서권 comparable 혼입 문제 우선 수정

인천계양 A6 69㎡

* 중요한 positive test
* 약 5.96억으로 preferred budget에 거의 정확히 들어오며 면적도 좋음
* 통근과 현지 comparable까지 양호하다면 consider로 올라갈 수 있어야 함

남양주왕숙2 A-3 59㎡

* 예상: watch ~ consider
* 신도시 미래가치를 과도하게 선반영하지 말 것

남양주왕숙2 A-3 74㎡

* 예상: watch 가능
* 예산 상단에 가까움

남양주왕숙2 A-3 84㎡

* 예상: pass
* stretch 7억 초과

성남복정2 A1 55~56㎡

* 예상: pass
* 입지 장점은 인정하되 7.9~8.1억으로 stretch 예산을 크게 초과
* SH 10년 선택권이 있는 사용자가 예산을 깨면서까지 살 명확한 이유가 없음

# 10. Gemini narrative 수정

위 upstream 수정이 끝난 뒤 Gemini prompt를 정리해라.

다음 표현을 반복하지 마라:

"세대수, 연식, 취득세, 등기/법무비, 확장비, 필수 옵션비, 통근 등이 확인불가이다."

사용자에게 실제 의사결정에 중요한 정보만 이야기해라.

좋은 예:

"분양가와 면적은 사용자 조건에 잘 맞는다. 다만 주요 업무지구 통근시간이 아직 평가되지 않아 최종 매수 판단의 확신도는 낮다."

또는:

"가격은 주변 생활권 대비 경쟁력이 있지만, 현재 사용자의 확장 예산을 초과하므로 안정적인 임대 거주권을 포기하며 무리할 이유는 부족하다."

또한:

watch = 보류
pass = 패스

로 표현을 통일한다.

"보류(pass)" 같이 의미가 충돌하는 표현은 금지한다.

# 11. 수정 후 검증

수정이 끝나면 위 5개 공고를 다시 regression test 해줘.

각 테스트에 대해 다음을 출력해라.

1. 대상 타입 / 가격
2. primary comparable로 실제 사용된 단지 목록
3. 각 comparable 선정 이유
4. benchmark
5. pooled median이 있다면 보조값
6. price ratio
7. 핵심 사용자 적합성
8. unknown 핵심 필드
9. verdict
10. confidence
11. verdict가 나온 핵심 이유 3개

특히 수정 전/후를 비교해서:

* comparable pool이 어떻게 바뀌었는지
* benchmark가 어떻게 바뀌었는지
* verdict가 왜 바뀌거나 유지됐는지

를 보여줘.

구현 후 결과를 임의로 좋은 방향으로 맞추지 말고,
데이터와 규칙에 따라 자연스럽게 나온 결과를 보여줘.
