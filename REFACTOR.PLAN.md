# analysis pipeline 소규모 리팩토링 설계 (책임 분리)

목표는 새 기능이 아니라 **책임 분리**다. `analyze.py`의 `analyze_property()`(현재 약 95줄의 단일 함수)가 source facts 수집 → comparable 선정 → 규칙 분석 → verdict → 보고서 조립을 한 번에 하고 있고, 그 과정에서 **verdict 문장이 upstream인 `user_fit`으로 흘러 들어가는 순환**이 생겼다. 기존 8개 회귀 케이스의 구조화 출력(verdict/ratio/benchmark/comparable)을 고정한 뒤, 한 단계씩 떼어낸다. 실제 코드 수정은 다음 프롬프트에서 진행한다.

## 0. 현재 문제 지점 (파일:줄 기준, `src/home_agent/analyze.py`)

| 문제 | 위치 | 설명 |
|---|---|---|
| 순환 의존 | 253 | `bad = reasons or ["현재 조회된 자료에서는 즉시 매수할 만큼 우월한 근거가 확인되지 않았습니다."]` — 이 문장은 verdict 결론인데 `user_fit.bad`/`weaknesses`에 들어가고, Gemini가 그대로 되풀이한다 |
| 역할 혼재 | 223~228, 243~250 | `reasons` 하나가 (a) verdict 하드네거티브, (b) `user_fit.bad`, (c) `rule_hits`, (d) report 문장 네 역할을 겸함. `repeats >= 2`(반복공급)는 status 결정 *뒤*에 append되어 verdict에는 영향 없지만 `rule_hits`에는 찍힘 — 일관성 없음 |
| 고정 요약문 | 259 | `verdict.summary`가 status와 무관하게 "보류가 기본입니다"로 하드코딩 (pass/consider에도 동일) |
| Q&A가 verdict 전에 생성 | 254 | Q7("SH 10년 사용자가 지금 살 정도로 좋은가")은 본질적으로 verdict 질문인데 verdict 결정과 무관하게 채워짐(대부분 "추가 확인 필요") |
| source 단계에 분석 로직 | 133~163 | `build_live_case()`가 면적 허용범위 필터(`same_area`)를 수행 — 이건 comparable 선정 책임 |
| 미사용 헬퍼 | `core.py:44,48` | `fact()`, `finding()`이 정의만 되어 있고 아무 데서도 안 쓰임 — PLAN.md 5절이 요구한 `Finding{code,kind,text,severity,rule_id}` 구조를 이번에 실제로 채택 |

## 1. 목표 파이프라인과 단계별 스키마

```
PropertyInput ─▶ [1 facts] CaseFacts ─▶ [2 comparables] ComparableSet
                                              │
                        profile/rules ────────▼
                                     [3 rules] RuleFindings ─▶ [4 verdict] Verdict
                                              │                      │
                                              └──────────┬───────────┘
                                                         ▼
                                   [5 presentation] AnalysisResult(JSON) ─▶ render_report / narrate(Gemini)
```
화살표는 단방향. **4(verdict)의 산출물은 5에서만 소비**되고 3 이하로는 절대 돌아가지 않는다.

스키마는 런타임 검증 없이 `TypedDict`로 `src/home_agent/schemas.py`에 문서화만 한다(현재 코드베이스가 dict 기반이라 pydantic 도입은 동작 변경 위험이 커서 이번 범위 밖).

### [1] CaseFacts — `facts.py` (현 `mock.build_case`, `analyze.build_live_case`)
```python
class CaseFacts(TypedDict):
    property: dict          # name, region, address, unit_type, exclusive_area_m2, price_krw,
                            # households, new_build, expected_move_in_ym, completion_year, property_type
    evidence: list[dict]
    transactions: list[dict]  # 후보 풀 전체(면적 필터 전). 각 항목: complex_name, area_m2, price_krw, year, region(동), evidence_ids
    sale_events: list[dict]
    new_supply: list[dict]; alternatives: list[dict]; location: dict
    status: Literal["ok", "partial", "unavailable", "insufficient_information"]
    warnings: list[str]
    search_scope: dict      # months_queried, extended_lookback, source_mode
```
변경점: `all_transactions`/`raw_transaction_count` 키를 없애고 `transactions` = 전체 풀로 통일. 면적 필터는 [2]로 이동. mock 쪽은 `_case()`의 `area_m2: max(area, 49)`가 [2]의 허용범위(±max(5, 15%))를 벗어나 케이스 A(37.35㎡)의 비교거래가 사라지므로, fixture를 `area_m2: area or 59`로 바꿔 필터가 no-op이 되게 한다(fixture 데이터 조정, 로직 아님).

### [2] ComparableSet — `comparables.py` (현 `_extract_dongs`, `_complex_groups`, `_group_comparables`, `_price_assessment`의 벤치마크 부분)
```python
class ComparableSet(TypedDict):
    target_dongs: list[str]
    same_area: list[ComplexGroup]     # tier 태깅된 단지 그룹 (표시용 상위 5)
    larger_area: list[ComplexGroup]
    benchmark: Benchmark              # reference_price_krw, tier_used, expanded, complexes_used(list[str]),
                                      # pooled_reference_price_krw, sample_count, raw_sample_count
    status: Literal["ok", "insufficient_information"]
```
`ComplexGroup` = 현재 `_complex_groups()` 출력 그대로(`comparable_tier`, `selection_reason`, `build_year_median`, min/median/max, sample_count). 벤치마크에 **실제 사용된 단지명 목록**(`complexes_used`)을 추가해 FIX.TODO 2번의 "debug 가능한 구조" 요구를 충족한다. 이 단계는 가격 *판정*(cheap/expensive)을 하지 않는다 — 숫자만 낸다.

### [3] RuleFindings — `rules.py` (현 197~228 + `_price_assessment`의 status 매핑)
```python
class Finding(TypedDict):  # core.finding() 재사용
    code: str               # e.g. "price.expensive", "area.below_40", "budget.over_stretch", "supply.repeated"
    kind: Literal["fact", "interpretation", "hypothesis", "missing_information"]
    text: str
    severity: Literal["info", "positive", "caution", "critical"]
    evidence_ids: list[str]; rule_id: str | None

class RuleFindings(TypedDict):
    price: PriceAssessment          # assessment, ratio_to_reference, ratio_to_reference_pooled + benchmark 필드 복사, reasoning
    score: Score                    # total, coverage_weight, provisional, components
    findings: list[Finding]         # 모든 판단 근거는 여기 한 곳에만
    core_missing: list[str]         # 세대수/입주예정월/통근 등 결측 (confidence 입력)
    costs: dict; finance: dict; sale_history: dict
    user_fit: {"good": list[str], "bad": list[str]}   # findings에서 파생: severity positive → good, caution/critical → bad
```
규칙:
- **하드 네거티브**는 `severity="critical"`(면적<40, stretch 예산 초과, 확인된 통근>60, 제외 주택유형). **반복공급**은 `severity="caution"`으로 재분류 — `user_fit.bad`에는 들어가되 verdict를 `pass`로 만들지 않는다(현재도 실제로는 그렇게 동작하므로 결과 불변, `rule_hits`에서만 빠짐).
- `user_fit.bad`에 verdict 결론 문장을 넣지 않는다. 하드네거티브가 없으면 `bad`는 비어 있을 수 있다 — "우월한 근거 없음"은 [4]의 summary가 말할 몫이다.
- `user_fit.good`도 사실에서만: `new_build`, 면적≥59 충족, 선호예산 이내 등 `severity="positive"` finding.

### [4] Verdict — `verdict.py` (현 230~250)
```python
class Verdict(TypedDict):
    status: Literal["avoid", "pass", "watch", "consider", "strong_buy_candidate"]
    confidence: float
    rule_hits: list[str]            # critical finding의 code 목록 (문장 아님)
    blocked_promotions: list[str]   # core_missing 그대로
    summary: str                    # status별 템플릿에서 생성
```
`decide_verdict(findings: RuleFindings, facts_status: str, mode: str) -> Verdict`. 로직은 지금 243~250과 동일(문턱값 변경 없음). `summary` 템플릿:
- pass: "핵심 조건 위반: {critical 텍스트들}" 
- watch: "핵심 조건 위반은 없지만, 가격판정 `{assessment}`(기준값 대비 {ratio}배)로 현재 임대 선택권을 포기할 만큼의 우위가 확인되지 않음"
- consider / strong_buy_candidate: 각각 PLAN.md 14.2 정의 문구

### [5] Presentation — `analyze.py`(조립) + `render_report` + `narrate.py`
- `analyze_property()`는 1→2→3→4를 호출하고 **기존 AnalysisResult JSON 키를 전부 그대로** 채우는 조립 함수만 남긴다(호출자 `main.py`, `daily_check.py`, `lookup.py` 무변경).
- `user_fit.questions`(Q1~Q10)는 조립 단계에서 채운다: Q1/Q2 ← price findings, Q5/Q6 ← positive/critical findings, Q7 ← `verdict.summary`(verdict→presentation 방향이므로 허용), 나머지는 해당 finding 없으면 지금처럼 "추가 확인 필요".
- 추가 키(호환 유지, additive): `findings[]`, `price_analysis.complexes_used`, `verdict.summary`(내용만 바뀜).
- `narrate.py`: 입력 축소 함수 `build_narrative_facts(result)`를 명시(현 `RELEVANT_KEYS`)하고 `findings`를 포함. 프롬프트의 "재계산 금지·설명만" 원칙 유지. `user_fit.bad`에서 verdict 문장이 사라지므로 Gemini가 매번 "우월한 근거가 확인되지 않았다"를 반복하던 현상은 자연히 없어진다.

## 2. 회귀 보존 방식 (먼저 한다)

현재 8개 케이스는 `scratchpad/regression.py`에서 **live API + Gemini**로만 돌아가 재현성이 없다(MOLIT 거래는 매일 늘고, Gemini는 비결정적). 리팩토링 전에 고정한다:

1. `scripts/record_regression_fixtures.py`(1회 실행): 8개 케이스에 대해 청약홈 notice/model JSON과 `molit.fetch_transactions_live()`의 **정규화된 결과**(월별 XML 원문이 아닌 `transactions` 리스트)를 `tests/fixtures/regression/<case>.json.gz`로 저장. 지역 5곳 × 12개월 정규화 거래는 수십만 행이 아니라 수천 행 수준이라 gzip으로 수백 KB.
2. `tests/test_regression_cases.py`: fixture 로더가 `applyhome.search_notices/fetch_house_models`, `molit.fetch_transactions_live`를 monkeypatch하고 `as_of`를 고정해 `analyze_property(mode="live")`를 오프라인 실행. 케이스별로 다음을 **스냅샷 assert**:
   `verdict.status`, `price_analysis.assessment`, `round(ratio_to_reference, 2)`, `reference_price_krw`, `benchmark_tier_used`, `benchmark_expanded`, primary same_area 단지명 목록, `missing_information`, `score.total`.
   기대값은 방금 실행한 회귀 출력(양주회천 59.74㎡ watch/2.01/178,000,000/primary … 성남복정2 pass/0.67/1,185,000,000)을 그대로 쓴다.
3. `scripts/regression_live.py`: 현 scratchpad 스크립트를 repo로 옮겨 Gemini 문장 확인용으로 유지(테스트 아님, 수동 실행).

이 스냅샷이 초록인 채로 아래 단계를 하나씩 진행한다. 텍스트 필드(`user_fit.bad`, `verdict.summary`, `report`)는 의도적으로 바뀌므로 assert 대상에서 제외한다.

## 3. 단계별 변경 (각 단계 = 별도 커밋, 매 단계 `pytest` + 회귀 스냅샷 통과)

| 단계 | 변경 | 동작 변화 | 완료 조건 |
|---|---|---|---|
| 0 | 회귀 fixture 기록 + `test_regression_cases.py` + `schemas.py`(TypedDict만) | 없음 | 8 케이스 스냅샷 초록 |
| 1 | `comparables.py` 신설: `_extract_dongs/_complex_groups/_group_comparables` 이동, 벤치마크 계산을 `select_comparables(facts, target) -> ComparableSet`로 분리. `_price_assessment`는 status 매핑만 남기고 [3]로 | 없음(순수 이동) | 스냅샷 동일 |
| 2 | `facts.py` 신설: `build_case`/`build_live_case`를 `collect_facts(inp, mode, ...) -> CaseFacts`로 통합, 면적 필터를 [2]로 이동, `all_transactions` 키 제거, mock fixture `area_m2` 조정 | mock 케이스의 비교거래 area 값만 변경(판정 불변) | test_core 4건 + 스냅샷 동일 |
| 3 | `rules.py` 신설: score/core_missing/하드네거티브/반복공급/costs/finance를 `evaluate_rules(...) -> RuleFindings`로. `reasons` 문자열 리스트 → `Finding` 리스트. `user_fit.good/bad`를 findings에서 파생, **verdict 문장 제거** | `user_fit.bad`·`weaknesses` 텍스트, `rule_hits`(반복공급 제외) 변경. verdict/ratio 불변 | 스냅샷 동일 |
| 4 | `verdict.py` 신설: `decide_verdict()`, status별 `summary` 템플릿 | `verdict.summary` 텍스트 변경 | 스냅샷 동일 |
| 5 | `analyze.py`를 조립 전용으로 축소, Q1~Q10을 조립 단계로 이동(Q7 ← verdict.summary), `render_report`가 findings 사용 | `report`·`questions` 텍스트 변경 | 스냅샷 동일, `narrate` 프롬프트에 `findings` 추가 후 `regression_live.py`로 문장 육안 확인 |

각 단계에서 **문턱값·가중치·필터 상수는 하나도 바꾸지 않는다.** 바뀌는 것은 코드 위치와 문장 생성 위치만이다.

## 4. 명시적으로 하지 않는 것
- verdict 문턱값, comparable tier 규칙, confidence 식 변경 (동작 보존이 목표)
- pydantic 런타임 검증 도입, async화, PLAN.md 3절의 전체 패키지 구조(`sources/`, `analysis/` 다층 디렉터리)로의 이동 — 5개 flat 모듈까지만
- Gemini 프롬프트의 의미 변경 (입력에 `findings`만 추가)
- `alternatives`/통근/confidence 엔진 등 FIX.TODO 잔여 항목

## 5. 다음 프롬프트에서의 실행 순서
0단계부터. 0단계는 live 호출이 한 번 필요하다(fixture 기록) — 그 뒤로는 전부 오프라인. 각 단계 끝에 `python -m pytest -q && python -m ruff check .` 결과와 스냅샷 diff를 보고한다.
