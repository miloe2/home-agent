"""Stage [4] of the analysis pipeline: verdict decision.

Reads Findings/price/score/confidence and produces a single Verdict. Nothing
downstream of this feeds back upstream - user_fit, score, and price_analysis
are already finalized by the time this runs. The reverse used to happen (a
verdict conclusion sentence was injected into user_fit.bad); that circular
dependency is exactly what this stage split was meant to remove.
"""
from __future__ import annotations

from typing import Any

_RATIO_LABEL = {"cheap": "쌈", "fair": "적정", "fair_to_expensive": "다소 비쌈", "expensive": "비쌈", "insufficient_information": "판정 불가"}


def _summarize(status: str, rule_hits: list[str], price_status: str, ratio: float | None) -> str:
    ratio_txt = f"{ratio:.2f}배" if ratio is not None else "확인불가"
    price_txt = f"가격판정 `{price_status}`({_RATIO_LABEL.get(price_status, price_status)}, 기준값 대비 {ratio_txt})"
    if status == "pass":
        return f"핵심 조건 위반으로 패스(탈락): {' / '.join(rule_hits)}"
    if status == "watch":
        return f"핵심 조건 위반은 없으나, {price_txt}로 현재 임대 선택권(SH 10년)을 포기할 만큼의 우위는 아직 확인되지 않아 보류."
    if status == "consider":
        return f"핵심 하드 조건을 충족하고 {price_txt} — 임대 유지와 비교해도 매수 검토 단계로 넘어갈 가치가 있음."
    if status == "strong_buy_candidate":
        return f"{price_txt}이며 핵심 정보가 대부분 확인됨 — 현재 10년 임대 선택권을 포기할 만큼 드문 우위로 판단됨(강력 매수 후보)."
    return "구조적 리스크가 확인되어 회피 대상."


def decide_verdict(
    findings: list[dict[str, Any]],
    core_missing: list[str],
    price_status: str,
    ratio: float | None,
    case_status: str,
    area: float | None,
    price: int | None,
    coverage: float,
    total: float | None,
    confidence: float,
) -> dict[str, Any]:
    critical = [f for f in findings if f["severity"] == "critical"]
    rule_hits = [f["text"] for f in critical]
    core_ok = area is not None and price is not None and price_status != "insufficient_information" and case_status == "ok"

    if critical:
        status = "pass"
    elif core_ok and price_status == "cheap" and coverage >= 85 and confidence >= 0.55 and total is not None and total >= 85:
        status = "strong_buy_candidate"
    elif core_ok and price_status in ("cheap", "fair") and coverage >= 70 and confidence >= 0.35 and (total is None or total >= 65):
        status = "consider"
    else:
        status = "watch"

    return {
        "status": status,
        "confidence": confidence,
        "rule_hits": rule_hits,
        "blocked_promotions": core_missing,
        "summary": _summarize(status, rule_hits, price_status, ratio),
    }
