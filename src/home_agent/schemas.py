"""Documentation-only TypedDicts for the analysis pipeline stages.

These are not enforced at runtime (the codebase stays dict-based to avoid a
pydantic migration risk mid-refactor - see REFACTOR.PLAN.md section 4). They
exist so each stage's input/output shape is written down in one place instead
of only living in analyze.py's dict literals.

    PropertyInput -> [facts.collect_facts] -> CaseFacts
                  -> [comparables.select_comparables] -> ComparableSet
                  -> [rules.evaluate_rules] -> RuleFindings
                  -> [verdict.decide_verdict] -> Verdict
                  -> [analyze.analyze_property assembly] -> AnalysisResult (JSON)

Verdict is consumed only by the assembly stage; nothing upstream of it reads
verdict.summary or verdict.status back into facts/comparables/rules.
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

CaseStatus = Literal["ok", "partial", "unavailable", "insufficient_information"]
ComparableTier = Literal["primary", "secondary"]
BenchmarkTierUsed = Literal["primary", "primary+secondary", "insufficient_for_benchmark"]
PriceAssessmentStatus = Literal["cheap", "fair", "fair_to_expensive", "expensive", "insufficient_information"]
FindingKind = Literal["fact", "interpretation", "hypothesis", "missing_information"]
FindingSeverity = Literal["info", "positive", "caution", "critical"]
VerdictStatus = Literal["avoid", "pass", "watch", "consider", "strong_buy_candidate"]


class CaseFacts(TypedDict):
    """Output of facts.collect_facts(). Source-of-truth data only - no comparisons, no scoring."""
    property: dict[str, Any]  # name, region, address, unit_type, exclusive_area_m2, price_krw,
                               # households, new_build, expected_move_in_ym, completion_year, property_type
    evidence: list[dict[str, Any]]
    transactions: list[dict[str, Any]]  # full candidate pool, unfiltered by area; comparables.py filters it
    sale_events: list[dict[str, Any]]
    new_supply: list[dict[str, Any]]
    alternatives: list[dict[str, Any]]
    location: dict[str, Any]
    status: CaseStatus
    warnings: list[str]
    search_scope: dict[str, Any]  # months_queried, extended_lookback


class ComplexGroup(TypedDict):
    complex_name: str
    region: str | None  # dong
    comparable_tier: ComparableTier
    selection_reason: list[str]
    sample_count: int
    area_m2_min: float | None
    area_m2_max: float | None
    build_year_median: int | None
    price_krw_min: int
    price_krw_median: int
    price_krw_max: int
    evidence_ids: list[str]


class Benchmark(TypedDict):
    reference_price_krw: int | None
    tier_used: BenchmarkTierUsed | None
    expanded: bool
    complexes_used: list[str]
    pooled_reference_price_krw: int | None
    sample_count: int
    raw_sample_count: int


class ComparableSet(TypedDict):
    target_dongs: list[str]
    same_area: list[ComplexGroup]
    larger_area: list[ComplexGroup]
    benchmark: Benchmark
    status: Literal["ok", "insufficient_information"]


class Finding(TypedDict):
    code: str
    kind: FindingKind
    text: str
    severity: FindingSeverity
    evidence_ids: list[str]
    rule_id: str | None


class RuleFindings(TypedDict):
    price: dict[str, Any]  # assessment, ratio_to_reference, ratio_to_reference_pooled, reasoning, benchmark fields
    score: dict[str, Any]  # total, coverage_weight, provisional, components
    findings: list[Finding]
    core_missing: list[str]
    costs: dict[str, Any]
    finance: dict[str, Any]
    user_fit: dict[str, list[str]]  # good, bad - derived from findings, never from verdict


class Verdict(TypedDict):
    status: VerdictStatus
    confidence: float
    rule_hits: list[str]
    blocked_promotions: list[str]
    summary: str
