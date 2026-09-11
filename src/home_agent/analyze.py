from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from . import comparables, facts, rules, verdict
from .core import clean_input, evidence, load_yaml, slug_for, utc_now

QUESTIONS = ["왜 이 가격인가?", "이 가격이 싼가, 적정한가, 비싼가?", "싼다면 왜 싼가?", "비싸다면 어떤 프리미엄 때문인가?", "사용자가 이 집을 사면 무엇을 얻는가?", "무엇을 포기하는가?", "SH에서 10년 기다릴 수 있는 사용자가 지금 살 정도로 좋은가?", "5~10년 실거주에 적합한가?", "향후 다른 사람이 사고 싶어할 상품인가?", "같은 돈으로 더 좋은 대안이 있는가?"]


def _price_assessment(target: dict[str, Any], benchmark: dict[str, Any]) -> dict[str, Any]:
    """Classify cheap/fair/expensive from a precomputed benchmark (comparables.compute_benchmark).

    This function only does the ratio->status judgment; comparable *selection*
    (which complexes, which tier, which fallback) already happened upstream in
    comparables.py so it can be inspected/debugged independently of this
    classification.
    """
    price = target.get("price_krw")
    ref = benchmark["reference_price_krw"]
    if not price or ref is None:
        return {
            "status": "insufficient_information",
            "reasoning": ["비교 가능한 실거래 자료가 부족합니다."],
            "ratio_to_reference": None,
            "reference_price_krw": None,
            "ratio_to_reference_pooled": None,
            "reference_price_krw_pooled": None,
            "benchmark_tier_used": None,
            "benchmark_expanded": False,
            "older_reference_price_krw": None,
            "older_ratio_to_reference": None,
            "benchmark_sensitive": False,
        }
    pooled_ref = benchmark["pooled_reference_price_krw"]
    tier_used, expanded = benchmark["tier_used"], benchmark["expanded"]
    older_ref = benchmark.get("older_reference_price_krw")
    ratio = price / ref
    pooled_ratio = price / pooled_ref
    older_ratio = (price / older_ref) if older_ref else None
    status = "cheap" if ratio <= .9 else "fair" if ratio <= 1.05 else "fair_to_expensive" if ratio <= 1.15 else "expensive"

    # If median-of-medians and pooled disagree by a lot, a single "expensive"/
    # "cheap" label overstates how confident that judgment actually is -
    # flag it so the report/narrative can say so instead of picking one number
    # and presenting it as settled.
    value_diff_pct = abs(ref - pooled_ref) / max(ref, pooled_ref) if max(ref, pooled_ref) else 0
    benchmark_sensitive = abs(ratio - pooled_ratio) >= 0.20 or value_diff_pct >= 0.20
    tier_desc = {
        "new_or_recent": "동일 생활권 신축/준신축(준공 10년 이내)",
        "primary": "동일 생활권(같은 동, 연식 무관)",
        "primary+secondary": "동일 생활권 표본 부족으로 인접 생활권까지 확장",
        "insufficient_for_benchmark": "단지별 표본 부족",
    }.get(tier_used, "확인불가")
    reasoning = [
        f"비교 거래 기준값({tier_desc}, {len(benchmark['complexes_used'])}개 단지 median의 median)은 {ref:,}원이고 대상 가격은 {price:,}원입니다 (배율 {ratio:.2f}배).",
        f"참고: 개별 거래 {benchmark['sample_count']}건을 그대로 모아 median을 내면 {pooled_ref:,}원(배율 {pooled_ratio:.2f}배)입니다 — 거래량이 많은 단지의 영향을 더 크게 반영한 값입니다.",
    ]
    if older_ref is not None and tier_used == "new_or_recent":
        reasoning.append(
            f"참고: 동일 생활권 구축(준공 10년 초과) 기준값은 {older_ref:,}원(배율 {older_ratio:.2f}배)입니다 — "
            "신축 분양가와 구축 시세를 같은 상품으로 비교하지 않도록 별도로 표시합니다."
        )
    if benchmark_sensitive:
        reasoning.append(
            "비교 방식(단지 동등취급 vs 개별거래 가중)에 따라 배율 차이가 커서, "
            "가격 프리미엄에 대한 판단의 확신도는 낮습니다."
        )
    return {
        "status": status,
        "reasoning": reasoning,
        "ratio_to_reference": ratio,
        "reference_price_krw": ref,
        "ratio_to_reference_pooled": pooled_ratio,
        "reference_price_krw_pooled": pooled_ref,
        "benchmark_tier_used": tier_used,
        "benchmark_expanded": expanded,
        "older_reference_price_krw": older_ref,
        "older_ratio_to_reference": older_ratio,
        "benchmark_sensitive": benchmark_sensitive,
    }


def analyze_property(property_input: dict[str, Any], *, config_dir: str = "config", as_of: str | None = None, mode: str = "mock") -> dict[str, Any]:
    inp = clean_input(property_input)
    config_path = Path(config_dir)
    profile_path = config_path / "user_profile.yaml"
    rules_path = config_path / "finance_rules.yaml"
    profile = load_yaml(profile_path)
    finance_rules = load_yaml(rules_path)
    resolved_as_of = as_of or utc_now()
    case = facts.collect_facts(inp, mode, config_path, resolved_as_of)
    p = dict(case["property"])
    for k in ("region", "address", "unit_type", "exclusive_area_m2", "price_krw", "property_type"):
        if inp.get(k) is not None: p[k] = inp[k]
    ev = list(case["evidence"])
    user_ev = evidence("user://property-input", "user_input", "input", mock=False); ev.append(user_ev)
    area = p.get("exclusive_area_m2"); price = p.get("price_krw")
    target_dongs = comparables.extract_dongs(p.get("region") or p.get("address"))
    as_of_year = int(resolved_as_of[:4]) if resolved_as_of else None
    comparable_set = comparables.select_comparables(case["transactions"], area, target_dongs, new_build=bool(p.get("new_build")), as_of_year=as_of_year)
    price_result = _price_assessment(p, comparable_set["benchmark"])
    price_status, price_reasons, ratio = price_result["status"], price_result["reasoning"], price_result["ratio_to_reference"]
    events = sorted(case["sale_events"], key=lambda x: x.get("event_date") or "")
    repeats = sum(x["event_type"] in {"resupply", "discretionary", "first_come", "unranked"} for x in events)
    history_findings = []
    if repeats >= 2: history_findings.append(f"잔여물량 또는 재공급 사건이 {repeats}회 확인되어 당시 수요 흡수가 원활하지 않았을 가능성이 있습니다.")
    else: history_findings.append("확인된 분양 이력만으로 반복 잔여물량 신호는 확인되지 않았습니다.")
    comp = [{"group": "same_area", **g} for g in comparable_set["same_area"]]
    larger = [{"group": "larger_area", **g} for g in comparable_set["larger_area"]]
    price_reasoning = price_reasons[:]
    if area and area < 40: price_reasoning.append("가격이 예산 안에 있어도 전용면적이 장기 실거주 기준보다 크게 작습니다.")
    assessment = {
        "asking_price": price, "effective_price": price, "assessment": price_status,
        "ratio_to_reference": ratio,
        "reference_price_krw": price_result["reference_price_krw"],
        "ratio_to_reference_pooled": price_result["ratio_to_reference_pooled"],
        "reference_price_krw_pooled": price_result["reference_price_krw_pooled"],
        "benchmark_tier_used": price_result["benchmark_tier_used"],
        "benchmark_expanded": price_result["benchmark_expanded"],
        "older_reference_price_krw": price_result["older_reference_price_krw"],
        "older_ratio_to_reference": price_result["older_ratio_to_reference"],
        "benchmark_sensitive": price_result["benchmark_sensitive"],
        "reasoning": price_reasoning, "provisional": price_status == "insufficient_information",
    }

    rule_findings = rules.evaluate_rules(p, profile, finance_rules, price_status, case["status"], repeats, mode, benchmark=price_result)
    coverage, total = rule_findings["score"]["coverage_weight"], rule_findings["score"]["total"]
    core_missing = rule_findings["core_missing"]
    good, bad = rule_findings["user_fit"]["good"], rule_findings["user_fit"]["bad"]

    v = verdict.decide_verdict(rule_findings["findings"], core_missing, price_status, ratio, case["status"], area, price, coverage, total, rule_findings["confidence"])

    # Q7 ("SH 10년 사용자가 지금 살 정도로 좋은가") is the one question that legitimately
    # quotes the verdict conclusion - everything else stays sourced from facts/rules.
    questions = []
    for i, q in enumerate(QUESTIONS):
        if i == 6:
            answer = v["summary"]
        elif i < 2 and price_reasoning:
            answer = price_reasoning[0]
        else:
            answer = "현재 자료로는 추가 확인이 필요합니다."
        questions.append({"id": f"Q{i+1}", "question": q, "answer": answer, "status": "partial" if core_missing else "supported", "evidence_ids": [x["id"] for x in ev], "rule_ids": []})

    report = render_report(p, v["status"], total, price_status, v["rule_hits"], good, bad, core_missing, events, comp, larger, rule_findings["finance"], mode)
    search_scope = "mock fixture" if mode == "mock" else "molit adapter only; LH/geocoding not connected"
    warnings = ["이 결과는 mock 합성자료를 사용한 시뮬레이션입니다."] if mode == "mock" else list(case.get("warnings", []))
    result = {"schema_version": "1.0", "analysis_id": str(uuid.uuid4()), "property_slug": slug_for({"name": p["name"], "region": p.get("region"), "unit_type": p["unit_type"]}), "analyzed_at": utc_now(), "as_of": resolved_as_of, "data_mode": mode, "simulation_only": mode == "mock", "profile_hash": hashlib.sha256(profile_path.read_bytes()).hexdigest(), "rules_hash": hashlib.sha256(rules_path.read_bytes()).hexdigest(), "property": p, "identity_status": "resolved" if case["status"] == "ok" else "unresolved", "verdict": v, "price_analysis": assessment, "sale_history": events, "sale_history_analysis": {"status": "ok", "repeated_supply_signal": repeats >= 2, "findings": history_findings}, "nearby_comparables": comp + larger, "comparable_analysis": {"status": comparable_set["status"], "sample_count": comparable_set["same_area_transaction_count"], "raw_sample_count": comparable_set["raw_transaction_count"], "search_scope": case.get("search_scope", {})}, "recent_new_supply_comparables": case["new_supply"], "new_supply_analysis": {"status": "unavailable", "search_scope": search_scope}, "alternatives": case["alternatives"], "alternatives_analysis": {"status": "unavailable", "search_scope": search_scope + " (동일 생활권 비교만 수행, 대체재 탐색 미구현)"}, "location_analysis": {"status": "ok" if case["location"] else "insufficient_information", **case["location"]}, "strengths": good, "weaknesses": bad, "user_fit": {"good": good, "bad": bad, "questions": questions}, "policy_finance": rule_findings["finance"], "score": rule_findings["score"], "evidence": ev, "findings": rule_findings["findings"], "conflicts": [], "data_quality": {"status": "synthetic_data" if mode == "mock" else "partial", "confidence_basis": "synthetic_data" if mode == "mock" else "available_sources", "missing": core_missing, "cost_breakdown_missing": rule_findings["costs"]["missing_cost_items"]}, "missing_information": core_missing, "warnings": warnings, "report": report}
    return result


def render_report(p: dict[str, Any], status: str, total: float | None, price_status: str, reasons: list[str], good: list[str], bad: list[str], missing: list[str], events: list[dict[str, Any]], comps: list[dict[str, Any]], larger: list[dict[str, Any]], finance: dict[str, Any], mode: str) -> str:
    good_lines = [f"- {x}" for x in good] or ["- 확인된 장점이 부족합니다."]
    bad_lines = [f"- {x}" for x in bad] or ["- 확인된 단점이 부족합니다."]
    comp_lines = [
        f"- [{x.get('comparable_tier', 'primary')}] {x.get('complex_name')}: {x.get('area_m2_min')}~{x.get('area_m2_max')}㎡ / "
        f"{x.get('price_krw_min'):,}~{x.get('price_krw_max'):,}원(중앙값 {x.get('price_krw_median'):,}원, {x.get('sample_count')}건, "
        f"준공중앙값 {x.get('build_year_median') or '확인불가'})"
        for x in comps + larger
    ] or ["- 비교 거래 자료 없음"]
    missing_lines = [f"- {x}" for x in missing] or ["- 핵심 결측 없음"]
    lines = ["# 내집마련 분석 보고서", "", f"> {'모의분석: 합성 fixture 기반' if mode == 'mock' else '실데이터 분석'}", "", f"## 결론: `{status}`", "", f"{p['name']} {p['unit_type']}은 가격판정 `{price_status}`입니다. 점수는 보조지표로 {total if total is not None else '산출 불가'}입니다.", "", "## 살 때 얻는 것", *good_lines, "", "## 살 때 포기하는 것", *bad_lines, "", "## 가격과 분양 이력", f"- 제시 가격: {p.get('price_krw') or '확인 필요'}원", *[f"- {e.get('event_date')}: {e.get('event_type')}" for e in events], "", "## 비교 자료", *comp_lines, "", "## 금융", f"- 정책대출 판단: {finance['status']}", "", "## 추가 확인사항", *missing_lines, "", "## 판단의 한계", "- 이 보고서는 점수보다 근거와 사용자 적합성 설명을 우선합니다.", "- 매수 전 공식 공고, 실제 비용, 금융기관 심사, 현장 상태를 별도로 확인해야 합니다."]
    return "\n".join(lines)
