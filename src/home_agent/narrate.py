from __future__ import annotations

import json
from typing import Any

try:
    from google import genai
except ImportError:  # optional dependency, pipeline works without it
    genai = None

MODEL = "gemini-flash-lite-latest"

STYLE_EXAMPLE = """서울 신축이고 4.4억이라 처음에는 싸 보이지만,
전용 37㎡라 장기 실거주에는 작은 편이다.
이 단지는 최초 분양 이후 잔여물량이 반복되어
시장이 이 가격을 강한 저가매력으로 평가하지 않았을 가능성이 있다.
반경/인근 생활권의 구축 59㎡는 대략 X~Y억이고,
비슷한 가격대의 다른 신규분양에는 50㎡ 이상도 존재한다.
따라서 SH에서 장기간 더 거주할 수 있는 사용자라면
서울 주소를 얻기 위해 면적을 이 정도까지 타협할 필요는 낮다."""

RELEVANT_KEYS = [
    "property",
    "verdict",
    "price_analysis",
    "sale_history_analysis",
    "nearby_comparables",
    "comparable_analysis",
    "strengths",
    "weaknesses",
    "user_fit",
    "findings",
    "score",
    "missing_information",
    "warnings",
]


def narrate(analysis_result: dict[str, Any], notice: dict[str, Any], api_key: str | None) -> str | None:
    if genai is None or not api_key:
        return None
    try:
        client = genai.Client(api_key=api_key)
        facts = {k: analysis_result.get(k) for k in RELEVANT_KEYS}
        prompt = f"""아래는 한 부동산 매물에 대해 이미 계산이 끝난 구조화 분석 결과(JSON)다.
이 안의 숫자·판정(verdict, price_analysis.assessment, score 등)은 절대 다시 계산하거나 바꾸지 마라.
JSON에 없는 사실은 지어내지 마라.

용어 규칙(반드시 지켜라):
- verdict.status의 "watch"는 한국어로 "보류"라고만 써라.
- verdict.status의 "pass"는 한국어로 "패스(탈락)"라고만 써라. "보류(pass)"처럼 두 뜻을 섞은 표현은 절대 쓰지 마라.
- "consider"는 "매수 검토 가치 있음", "strong_buy_candidate"는 "강력 매수 후보"로 써라.

nearby_comparables의 각 항목에는 comparable_tier(primary=동일 생활권, secondary=인접 생활권)와
selection_reason이 들어있다. 서술할 때 이 둘을 구분해라: primary는 "현지 시세"로,
secondary는 "참고용 인접 비교"로 다르게 취급하고, 서로 다른 생활권 시세를 뒤섞어
"이 지역이 싸다/비싸다"를 단정하지 마라.

missing_information에는 이제 정말 중요한 항목(세대수/입주예정월/통근)만 들어있다.
이것들만 언급하고, 취득세·등기법무비·확장비·필수옵션비 같은 부대비용 항목은
verdict를 바꿀 만큼 특이한 사정이 없는 한 언급하지 마라 — 매번 나열하면 신호 대비 잡음이 커진다.
new_build가 true면 "연식 확인불가"라고 쓰지 말고, expected_move_in_ym이 있으면 입주 시점을 언급하고
없으면 "입주예정월 확인불가"라고 써라.

price_analysis.benchmark_sensitive가 true이면, 단지 동등취급(median-of-medians)과 개별거래
가중(pooled) 두 계산 방식의 배율(ratio_to_reference vs ratio_to_reference_pooled) 차이가 크다는
뜻이다. 이 경우 가격 판정을 하나의 확정된 사실처럼 단정하지 말고, "비교 방식에 따라 평가가
달라 가격 프리미엄 판단의 확신도는 낮다"는 취지를 반드시 반영해라. false이면 이 얘기를 굳이
꺼내지 않아도 된다.

너의 역할은 이 JSON 안의 사실들을 서로 연결해서, 아래 예시와 같은 **연쇄적 판단 서술**을 4~7문장으로 쓰는 것이다:
- 첫인상(가격이 싸/적정/비싸 보이는가) → 그 인상을 깨거나 뒷받침하는 조건(면적, 반복공급 등 market signal)
  → primary 비교단지 시세를 구체적으로 언급(있다면 secondary는 참고로만)
  → 사용자 프로필 맥락(user_fit.good/bad, 특히 SH 10년 거주 여유·장기실거주 등)과 연결
  → 결론(이 조건이면 지금 이 타협을 할 필요가 있는가)

예시 문체(내용은 다른 매물 것이니 그대로 베끼지 말고 구조만 참고):
\"\"\"{STYLE_EXAMPLE}\"\"\"

분석 결과 JSON:
{json.dumps(facts, ensure_ascii=False, indent=2, default=str)}
"""
        response = client.interactions.create(model=MODEL, input=prompt)
        return response.output_text
    except Exception:  # noqa: BLE001 - narration is best-effort and must never break the scan
        return None
