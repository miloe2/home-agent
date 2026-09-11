"""Offline regression snapshot for the 8 real cases used to validate FIX.TODO.md.

Fixtures (tests/fixtures/regression/*.json.gz) freeze the PropertyInput derived
from a real 청약홈 notice + the exact molit.fetch_transactions_live() result for
that property's region, recorded by scripts/record_regression_fixtures.py.
Replaying them here avoids depending on live MOLIT data (which changes daily)
or Gemini (non-deterministic) - only the deterministic analyze_property()
pipeline is under test.

Only structural/numeric fields are asserted. Free-text fields (user_fit.bad,
verdict.summary, report) are expected to change across the refactor stages in
REFACTOR.PLAN.md and are intentionally not snapshotted here.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from home_agent import molit
from home_agent.analyze import analyze_property

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "regression"
CONFIG_DIR = str(Path(__file__).parents[1] / "config")


def _load_fixture(name: str) -> dict:
    with gzip.open(FIXTURE_DIR / f"{name}.json.gz", "rt", encoding="utf-8") as f:
        return json.load(f)


def _run(fixture: dict, monkeypatch) -> dict:
    monkeypatch.setattr(molit, "fetch_transactions_live", lambda *a, **k: fixture["molit_result"])
    return analyze_property(fixture["property_input"], config_dir=CONFIG_DIR, as_of=fixture["as_of"], mode="live")


def _primary_same_area_names(result: dict) -> list[str]:
    return [c["complex_name"] for c in result["nearby_comparables"] if c["group"] == "same_area" and c["comparable_tier"] == "primary"]


def _secondary_same_area_names(result: dict) -> list[str]:
    return [c["complex_name"] for c in result["nearby_comparables"] if c["group"] == "same_area" and c["comparable_tier"] == "secondary"]


#: user_fit.good/bad must only ever contain factual Findings (rules.py), never
#: a verdict conclusion sentence fed back upstream - that circularity (bad ->
#: verdict=watch because bad was non-empty) is exactly what rules.py/verdict.py
#: were split apart to remove. This is a structural guard, not a text
#: snapshot: it doesn't pin the exact wording, just bans conclusion phrasing.
_CIRCULAR_VERDICT_PHRASES = ["즉시 매수할 만큼", "보류가 적절", "지금 살 이유", "우월한 근거가 확인되지 않"]


def _assert_no_circular_verdict_text(result: dict) -> None:
    for text in result["user_fit"]["good"] + result["user_fit"]["bad"]:
        assert not any(p in text for p in _CIRCULAR_VERDICT_PHRASES), f"verdict-conclusion text leaked into user_fit: {text!r}"


CASES = [
    {
        "fixture": "yangju_hoecheon_59",
        "confidence": 0.88,
        "verdict_status": "watch",
        "assessment": "expensive",
        "ratio": 2.01,
        "reference_price_krw": 178_000_000,
        "tier_used": "primary",
        "expanded": False,
        "primary_names": ["덕정역서희스타힐스에듀포레뷰", "봉우마을(주공5단지)", "명지", "양주서희스타힐스2단지", "한국(101.102.103동)"],
        "missing": ["통근"],
        "score_total": 78.8,
        "rule_hits": [],
        "benchmark_sensitive": True,
    },
    {
        "fixture": "uijeongbu_ujeong_59",
        "confidence": 0.88,
        "verdict_status": "watch",
        "assessment": "expensive",
        "ratio": 1.87,
        "reference_price_krw": 217_500_000,
        "tier_used": "primary",
        "expanded": False,
        "primary_names": ["녹양힐스테이트", "청구", "대림", "신도9"],
        "missing": ["통근"],
        "score_total": 75.9,
        "rule_hits": [],
        "benchmark_sensitive": True,
    },
    {
        "fixture": "incheon_gyeyang_59",
        "confidence": 0.88,
        "verdict_status": "watch",
        "assessment": "expensive",
        "ratio": 1.74,
        "reference_price_krw": 308_000_000,
        "tier_used": "primary",
        "expanded": False,
        "primary_names": ["학마을영남", "학마을서해", "학마을한진", "학마을서원", "아주"],
        "missing": ["통근"],
        "score_total": 78.8,
        "rule_hits": [],
        "benchmark_sensitive": True,
    },
    {
        "fixture": "incheon_gyeyang_69",
        "confidence": 0.88,
        "verdict_status": "watch",
        "assessment": "expensive",
        "ratio": 1.91,
        "reference_price_krw": 312_500_000,
        "tier_used": "primary",
        "expanded": False,
        "primary_names": ["학마을영남", "학마을서해", "학마을한진", "학마을서원", "한진해모로"],
        "missing": ["통근"],
        "score_total": 78.8,
        "rule_hits": [],
        "benchmark_sensitive": True,
    },
    {
        "fixture": "namyangju_wangsuk_59",
        "confidence": 0.72,
        "verdict_status": "watch",
        "assessment": "expensive",
        "ratio": 2.00,
        "reference_price_krw": 263_500_000,
        "tier_used": "primary+secondary",
        "expanded": True,
        "primary_names": [],
        "secondary_names_subset": ["다산푸르지오", "평내호평역대명루첸포레스티움", "평내마을주공"],
        "missing": ["통근"],
        "score_total": 78.8,
        "rule_hits": [],
        "benchmark_sensitive": True,
    },
    {
        "fixture": "namyangju_wangsuk_74",
        "confidence": 0.72,
        "verdict_status": "watch",
        "assessment": "expensive",
        "ratio": 1.54,
        "reference_price_krw": 420_000_000,
        "tier_used": "primary+secondary",
        "expanded": True,
        "primary_names": [],
        "secondary_names_subset": ["e편한세상 다산", "다산롯데캐슬", "다산 이편한세상자이"],
        "missing": ["통근"],
        "score_total": 67.1,
        "rule_hits": [],
        "benchmark_sensitive": True,
    },
    {
        "fixture": "namyangju_wangsuk_84",
        "confidence": 0.75,
        "verdict_status": "pass",
        "assessment": "expensive",
        "ratio": 1.72,
        "reference_price_krw": 425_000_000,
        "tier_used": "primary+secondary",
        "expanded": True,
        "primary_names": [],
        "secondary_names_subset": ["e편한세상 다산", "다산롯데캐슬", "다산 이편한세상자이"],
        "missing": ["통근"],
        "score_total": 55.3,
        "rule_hits": ["사용자의 확장 예산을 초과합니다."],
        "benchmark_sensitive": True,
    },
    {
        # Bug Fix #1 (comparable recency bucketing): 4 of the 5 primary complexes
        # are recent (2020-2024); only 한신 (built 1990) is "older" and is now
        # excluded from the main benchmark - a 36-year-old complex isn't a
        # meaningful price comparison for a 2030 move-in new-build. This is the
        # one case (of 8) where the recency fix actually changes the benchmark;
        # see comparables.compute_benchmark's new_or_recent tier.
        "fixture": "seongnam_bokjeong_55",
        "confidence": 0.95,
        "verdict_status": "pass",
        "assessment": "cheap",
        "ratio": 0.65,
        "reference_price_krw": 1_230_000_000,
        "tier_used": "new_or_recent",
        "expanded": False,
        "primary_names": ["산성역자이푸르지오1단지", "산성역자이푸르지오2단지", "산성역포레스티아", "산성역자이푸르지오3단지", "한신"],
        "missing": ["통근"],
        "score_total": 69.4,
        "rule_hits": ["사용자의 확장 예산을 초과합니다."],
        # unlike the other 7 cases, median-of-medians (0.65x) and pooled (0.71x)
        # agree closely here - both say cheap, so this one is NOT flagged sensitive.
        "benchmark_sensitive": False,
    },
]


@pytest.mark.parametrize("case", CASES, ids=[c["fixture"] for c in CASES])
def test_regression_case(case, monkeypatch):
    fixture = _load_fixture(case["fixture"])
    result = _run(fixture, monkeypatch)

    assert result["verdict"]["status"] == case["verdict_status"]
    assert result["verdict"]["confidence"] == case["confidence"]
    assert result["verdict"]["rule_hits"] == case["rule_hits"]
    assert result["price_analysis"]["assessment"] == case["assessment"]
    assert round(result["price_analysis"]["ratio_to_reference"], 2) == case["ratio"]
    assert result["price_analysis"]["reference_price_krw"] == case["reference_price_krw"]
    assert result["price_analysis"]["benchmark_tier_used"] == case["tier_used"]
    assert result["price_analysis"]["benchmark_expanded"] == case["expanded"]
    assert result["price_analysis"]["benchmark_sensitive"] == case["benchmark_sensitive"]
    _assert_no_circular_verdict_text(result)
    assert result["missing_information"] == case["missing"]
    assert result["score"]["total"] == case["score_total"]
    assert _primary_same_area_names(result) == case["primary_names"]
    if "secondary_names_subset" in case:
        secondary = _secondary_same_area_names(result)
        for name in case["secondary_names_subset"]:
            assert name in secondary
