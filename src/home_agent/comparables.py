"""Stage [2] of the analysis pipeline: comparable selection.

Groups raw MOLIT transactions into per-complex summaries, tags each complex
primary/secondary by dong match against the target property's own address,
and computes the price benchmark (median-of-medians) used for the price
ratio. This stage only produces numbers - it does not judge cheap/expensive
(that's rules.py's job) and it does not decide verdict.
"""
from __future__ import annotations

import re
from typing import Any

_DONG_RE = re.compile(r"[가-힣0-9]+")

#: below this many complexes (with >=min_count transactions each) or this
#: many total transactions, the primary-tier benchmark is considered too thin
#: and falls back to primary+secondary (PLAN.md 9.3's "최소 2단지·3거래"). The
#: same threshold is reused per recency bucket below.
MIN_PRIMARY_COMPLEXES = 2
MIN_PRIMARY_TRANSACTIONS = 3
DISPLAY_LIMIT = 5

#: PLAN.md 9.2's own new_or_recent boundary (준공 0~10년). A pre-sale new-build
#: target is not well represented by 20-30 year old comparables in the same
#: dong; recency needs its own bucket, separate from same-dong/adjacent-dong tier.
RECENT_MAX_AGE_YEARS = 10


def _median(values: list[int]) -> int:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 == 1 else (s[mid - 1] + s[mid]) // 2


def extract_dongs(address: str | None) -> set[str]:
    tokens = _DONG_RE.findall(address or "")
    return {t for t in tokens if len(t) >= 2 and t.endswith(("동", "읍", "면"))}


def _tag_tier(dong: str | None, target_dongs: set[str]) -> str:
    return "primary" if dong and dong in target_dongs else "secondary"


def _tag_recency(build_year_median: int | None, as_of_year: int | None) -> str | None:
    if build_year_median is None or as_of_year is None:
        return None
    return "recent" if (as_of_year - build_year_median) <= RECENT_MAX_AGE_YEARS else "older"


def complex_groups(transactions: list[dict[str, Any]], target_dongs: set[str], *, min_count: int = 2, as_of_year: int | None = None) -> list[dict[str, Any]]:
    """Group transactions by complex and tag each group primary/secondary by dong match.

    Groups with fewer than `min_count` transactions are dropped - a single
    outlier transaction should not stand in for a whole complex's price level.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for t in transactions:
        name = t.get("complex_name") or "확인된 단지"
        groups.setdefault(name, []).append(t)
    result = []
    for name, rows in groups.items():
        if len(rows) < min_count:
            continue
        prices = sorted(x["price_krw"] for x in rows if x.get("price_krw"))
        if not prices:
            continue
        areas = [x["area_m2"] for x in rows if x.get("area_m2") is not None]
        years = [x["year"] for x in rows if x.get("year") is not None]
        evidence_ids = sorted({eid for x in rows for eid in x.get("evidence_ids", [])})
        dong = rows[0].get("region")
        tier = _tag_tier(dong, target_dongs)
        build_year_median = _median(years) if years else None
        selection_reason = ["same_dong" if tier == "primary" else "same_city_different_dong", "similar_area"]
        recency = _tag_recency(build_year_median, as_of_year)
        if recency:
            selection_reason.append(recency)
        result.append({
            "complex_name": name,
            "region": dong,
            "comparable_tier": tier,
            "recency": recency,
            "selection_reason": selection_reason,
            "sample_count": len(rows),
            "area_m2_min": min(areas) if areas else None,
            "area_m2_max": max(areas) if areas else None,
            "build_year_median": build_year_median,
            "price_krw_min": prices[0],
            "price_krw_median": prices[len(prices) // 2],
            "price_krw_max": prices[-1],
            "evidence_ids": evidence_ids,
        })
    return result


def group_comparables(transactions: list[dict[str, Any]], target_dongs: set[str], *, limit: int = DISPLAY_LIMIT, as_of_year: int | None = None) -> list[dict[str, Any]]:
    """Top-N complexes for display (nearby_comparables), primary tier first."""
    groups = complex_groups(transactions, target_dongs, min_count=2, as_of_year=as_of_year)
    groups.sort(key=lambda g: (g["comparable_tier"] != "primary", -g["sample_count"]))
    return groups[:limit]


def _sufficient(groups: list[dict[str, Any]]) -> bool:
    return len(groups) >= MIN_PRIMARY_COMPLEXES and sum(g["sample_count"] for g in groups) >= MIN_PRIMARY_TRANSACTIONS


def compute_benchmark(same_area_tx: list[dict[str, Any]], target_dongs: set[str], *, new_build: bool = False, as_of_year: int | None = None) -> dict[str, Any]:
    """Compute the price reference (median-of-medians) from same-area transactions.

    For an existing (non-new-build) property, this is unchanged from before:
    prefer primary-tier (same dong) complexes, falling back to
    primary+secondary when the primary pool is too thin (PLAN.md 9.3).

    For a new-build (청약 분양) target, a 20-30 year old same-dong complex is
    not a meaningful price comparison on its own - it's exposed here as an
    *older_reference_price_krw* data point, not folded silently into the main
    benchmark. The main benchmark prefers same-dong recent/semi-new complexes
    first (new_or_recent); if that pool is too thin it falls back to the exact
    same tier ladder used for existing properties (same-dong any age, then
    same-city other dongs). Recency is deliberately NOT used to justify
    reaching into other dongs ahead of that fallback - an earlier version of
    this function did that (secondary tier filtered to "recent" only) and it
    pulled in a materially different, much pricier sub-area (e.g. 다산동 for a
    남양주왕숙 target) as if it were a same-product comparison, which is the
    same class of mistake the primary/secondary dong split was built to avoid.

    Returns None reference values (status="insufficient_information") when
    there's no priceable data at all.
    """
    valid = [x for x in same_area_tx if x.get("price_krw")]
    if not valid:
        return {
            "reference_price_krw": None,
            "tier_used": None,
            "expanded": False,
            "complexes_used": [],
            "pooled_reference_price_krw": None,
            "sample_count": 0,
            "raw_sample_count": 0,
            "older_reference_price_krw": None,
            "older_complexes_used": [],
        }
    groups = complex_groups(valid, target_dongs, min_count=2, as_of_year=as_of_year)
    primary = [g for g in groups if g["comparable_tier"] == "primary"]
    primary_older = [g for g in primary if g["recency"] == "older"]
    older_ref = _median([g["price_krw_median"] for g in primary_older]) if _sufficient(primary_older) else None

    used, tier_used, expanded = None, None, False
    if new_build and as_of_year is not None:
        primary_recent = [g for g in primary if g["recency"] == "recent"]
        if _sufficient(primary_recent):
            used, tier_used, expanded = primary_recent, "new_or_recent", False

    if used is None:
        if _sufficient(primary):
            used, tier_used, expanded = primary, "primary", False
        elif groups:
            used, tier_used, expanded = groups, "primary+secondary", True
        else:
            used, tier_used, expanded = [], "insufficient_for_benchmark", True

    pooled_ref = _median([x["price_krw"] for x in valid])
    ref = _median([g["price_krw_median"] for g in used]) if used else pooled_ref
    return {
        "reference_price_krw": ref,
        "tier_used": tier_used,
        "expanded": expanded,
        "complexes_used": [g["complex_name"] for g in used],
        "pooled_reference_price_krw": pooled_ref,
        "sample_count": len(valid),
        "raw_sample_count": len(same_area_tx),
        "older_reference_price_krw": older_ref,
        "older_complexes_used": [g["complex_name"] for g in primary_older] if older_ref is not None else [],
    }


def filter_same_area(transactions: list[dict[str, Any]], area: float | None) -> list[dict[str, Any]]:
    """PLAN.md 9.2 same_area rule: area diff <= max(5m2, target area * 15%)."""
    if not area:
        return transactions
    tol = max(5.0, area * 0.15)
    return [t for t in transactions if t.get("area_m2") is not None and abs(t["area_m2"] - area) <= tol]


def filter_larger_area(transactions: list[dict[str, Any]], area: float | None) -> list[dict[str, Any]]:
    """PLAN.md 9.2 larger_area rule: at least 8m2 bigger than the target."""
    if not area:
        return []
    return [t for t in transactions if t.get("area_m2") is not None and t["area_m2"] >= area + 8]


def select_comparables(all_transactions: list[dict[str, Any]], area: float | None, target_dongs: set[str], *, new_build: bool = False, as_of_year: int | None = None) -> dict[str, Any]:
    same_area_tx = filter_same_area(all_transactions, area)
    larger_pool = filter_larger_area(all_transactions, area)
    return {
        "target_dongs": sorted(target_dongs),
        "same_area": group_comparables(same_area_tx, target_dongs, as_of_year=as_of_year),
        "larger_area": group_comparables(larger_pool, target_dongs, as_of_year=as_of_year),
        "benchmark": compute_benchmark(same_area_tx, target_dongs, new_build=new_build, as_of_year=as_of_year),
        "status": "ok" if same_area_tx else "insufficient_information",
        "same_area_transaction_count": len(same_area_tx),
        "raw_transaction_count": len(all_transactions),
    }
