"""Stage [3] of the analysis pipeline: rule-based judgment.

Turns facts + comparable benchmark into scored components and Findings. This
stage does not decide verdict.status - it only produces the evidence verdict.py
(stage [4]) will use. Critically, `user_fit.good/bad` here comes *only* from
Findings, never from a verdict conclusion sentence - upstream stages must
never quote a downstream decision.
"""
from __future__ import annotations

from typing import Any

from .core import deep_get, finding


def _score_components(p: dict[str, Any], profile: dict[str, Any], price_status: str) -> list[dict[str, Any]]:
    area = p.get("exclusive_area_m2")
    price = p.get("price_krw")
    households = p.get("households")
    new_build = p.get("new_build")
    year = p.get("completion_year")
    commute = p.get("commute_minutes")
    workplace_known = deep_get(profile, "property_preferences.commute.workplace_address") is not None

    def component(cid: str, weight: int, value: float | None, reasoning: str) -> dict[str, Any]:
        return {"id": cid, "weight": weight, "value": value, "reasoning": reasoning, "evidence_ids": []}

    market_score = {"cheap": 100, "fair": 75, "fair_to_expensive": 40, "expensive": 10}.get(price_status)
    commute_score = None if not workplace_known else (None if commute is None else (100 if commute <= 40 else 70 if commute <= 60 else 10))
    return [
        component("area", 30, None if area is None else (10 if area < 40 else 40 if area < 50 else 80 if area < 59 else 100), "사용자 프로필의 장기 실거주 면적 기준"),
        component("budget", 20, None if price is None else (100 if price <= profile["budget"]["preferred_max_price_krw"] else 50 if price <= profile["budget"]["stretch_max_price_krw"] else 0), "선호·확장 예산 기준"),
        component("market_price", 20, market_score, "주변 비교거래 기준"),
        component("commute", 15, commute_score, "door-to-door 직장 경로(다중 업무지구 평가는 미구현)"),
        component("complex", 10, None if households is None else (20 if households < 150 else 50 if households < 300 else 75 if households < 500 else 100), "세대수와 관리·거래 유동성의 보조 지표"),
        component("age", 5, 100 if new_build or year is not None else None, "신축 선호(신규 분양은 new_build 기준, 기존 아파트는 준공연도 기준)"),
    ]


#: how much each benchmark tier is trusted as a same-product price comparison,
#: independent of how many core property fields happen to be known. A
#: same-dong (or same-dong-recent) match is a direct comparison; falling back
#: to primary+secondary means the tool had to reach outside the immediate
#: area, and no benchmark at all means the ratio/assessment is barely more
#: than a guess.
_TIER_QUALITY = {
    "new_or_recent": 1.0,
    "primary": 1.0,
    "primary+secondary": 0.6,
    "insufficient_for_benchmark": 0.2,
}
_HARD_RULE_CONFIDENCE_FLOOR = 0.75


def _compute_confidence(
    mode: str,
    case_status: str,
    area: float | None,
    price: int | None,
    households: int | None,
    new_build: bool | None,
    move_in_ym: str | None,
    year: int | None,
    benchmark: dict[str, Any],
    has_critical_finding: bool,
) -> float:
    """Confidence in the analysis, not in a successful purchase.

    Two independent things can make an analysis trustworthy: (1) the core
    property fields are actually known (completeness), and (2) the price
    benchmark is a same-product comparison rather than a thin fallback
    (market data quality). A verdict driven by a hard rule (e.g. clear budget
    overage) is highly certain regardless of how thin the comparable pool is
    - price/budget are directly known facts, not estimates - so that case
    gets a confidence floor instead of being dragged down by comparable
    quality that isn't actually load-bearing for that verdict.
    """
    if mode == "mock":
        return 0.0
    completeness_checks = [
        area is not None, price is not None, households is not None,
        (move_in_ym is not None) if new_build else (year is not None),
        case_status == "ok",
    ]
    completeness = sum(completeness_checks) / len(completeness_checks)

    tier_used = benchmark.get("benchmark_tier_used")
    market_quality = _TIER_QUALITY.get(tier_used, 0.2 if tier_used else 0.1)
    if benchmark.get("benchmark_sensitive"):
        market_quality *= 0.75

    confidence = 0.5 * completeness + 0.5 * market_quality
    if has_critical_finding:
        confidence = max(confidence, _HARD_RULE_CONFIDENCE_FLOOR)
    return round(min(confidence, 0.95), 2)


def evaluate_rules(
    p: dict[str, Any],
    profile: dict[str, Any],
    finance_rules: dict[str, Any],
    price_status: str,
    case_status: str,
    repeats: int,
    mode: str,
    benchmark: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`benchmark` is analyze._price_assessment()'s return dict (benchmark_tier_used,
    benchmark_expanded, benchmark_sensitive) - only used here to gauge confidence
    in the price comparison, never to re-derive price_status itself."""
    area = p.get("exclusive_area_m2")
    price = p.get("price_krw")
    households = p.get("households")
    year = p.get("completion_year")
    new_build = p.get("new_build")
    move_in_ym = p.get("expected_move_in_ym")
    commute = p.get("commute_minutes")
    workplace_known = deep_get(profile, "property_preferences.commute.workplace_address") is not None

    components = _score_components(p, profile, price_status)
    known = [c for c in components if c["value"] is not None]
    coverage = sum(c["weight"] for c in known)
    total = round(sum(c["value"] * c["weight"] for c in known) / coverage, 1) if coverage >= 60 else None

    # core_missing drives confidence and the user-facing report; cost-breakdown
    # unknowns (취득세/등기법무비/확장비/필수옵션비) stay inside `costs` only,
    # unless they change a verdict.
    core_missing = []
    if area is None: core_missing.append("전용면적")
    if price is None: core_missing.append("가격")
    if households is None: core_missing.append("세대수")
    if new_build and move_in_ym is None: core_missing.append("입주예정월")
    elif not new_build and year is None: core_missing.append("연식")
    if price_status == "insufficient_information": core_missing.append("비교 거래")
    if not workplace_known: core_missing.append("통근")

    findings = []
    if area is not None and area < 40:
        findings.append(finding("area.below_40", "fact", "전용면적이 40㎡ 미만이라 부부 장기 실거주에 큰 타협입니다.", severity="critical"))
    if price is not None and price > profile["budget"]["stretch_max_price_krw"]:
        findings.append(finding("budget.over_stretch", "fact", "사용자의 확장 예산을 초과합니다.", severity="critical"))
    if commute is not None and workplace_known and commute > 60:
        findings.append(finding("commute.over_60", "fact", "확인된 통근시간이 60분을 초과합니다.", severity="critical"))
    if p.get("property_type") in deep_get(profile, "property_preferences.property_type.exclude", []):
        findings.append(finding("property_type.excluded", "fact", "사용자가 제외한 주택 유형입니다.", severity="critical"))
    if repeats >= 2:
        findings.append(finding("supply.repeated", "interpretation", "반복 재공급은 가격 수요에 대한 추가 확인이 필요합니다.", severity="caution"))
    if new_build or p.get("completion_year"):
        findings.append(finding("product.new_build", "fact", "신축 상품과 확인된 입지·예산 적합성", severity="positive"))

    good = [f["text"] for f in findings if f["severity"] == "positive"]
    bad = [f["text"] for f in findings if f["severity"] in ("caution", "critical")]

    has_critical_finding = any(f["severity"] == "critical" for f in findings)
    confidence = _compute_confidence(
        mode, case_status, area, price, households, new_build, move_in_ym, year,
        benchmark or {}, has_critical_finding,
    )

    costs = {"asking_price": price, "effective_price": price, "total_acquisition_cost": None, "required_equity": None, "is_complete": False, "missing_cost_items": ["취득세", "등기/법무비", "확장비", "필수 옵션비"]}
    finance = {"status": "insufficient_information", "programs": [{"id": x["id"], "status": "insufficient_information", "reason": "공식 규칙 검증 및 소득·자산 입력이 없습니다.", "source_urls": x.get("source_urls", [])} for x in finance_rules.get("programs", [])], "approval_confirmed": False, "approved_amount_krw": None, "missing_fields": ["공식 정책 기준", "세전소득", "순자산"]}

    return {
        "score": {"total": total, "coverage_weight": coverage, "provisional": total is None, "components": components},
        "findings": findings,
        "core_missing": core_missing,
        "confidence": confidence,
        "costs": costs,
        "finance": finance,
        "user_fit": {"good": good, "bad": bad},
    }
