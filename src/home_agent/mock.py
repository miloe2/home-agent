from __future__ import annotations

from typing import Any

from .core import evidence


def build_case(inp: dict[str, Any]) -> dict[str, Any]:
    name = inp["name"]
    if "테스트 서울" in name or "개봉" in name:
        return _case("서울", 37.35, 446_000_000, 500, 2025, 25, "테스트 서울 소형 A", repeated=True)
    if "테스트 부천" in name or "부천" in name:
        return _case("경기 부천", 52, 430_000_000, 150, 2025, 20, "테스트 부천 B")
    if "테스트 구리" in name or "구리" in name:
        return _case("경기 구리", 38, 670_000_000, 3000, 2026, 5, "테스트 구리 C")
    if "테스트 외곽" in name or "남양주" in name:
        return _case("경기 남양주 외곽", 59, 500_000_000, 800, 2025, 80, "테스트 외곽 D")
    return _case(inp.get("region", "미상"), inp.get("exclusive_area_m2"), inp.get("price_krw"), None, None, None, name, missing=True)


def _case(region: str, area: float | None, price: int | None, households: int | None, year: int | None, commute: int | None, name: str, *, repeated: bool = False, missing: bool = False) -> dict[str, Any]:
    e = evidence(f"fixture://{name}", excerpt="합성 테스트 데이터")
    events = [{"event_type": "initial_sale", "event_date": "2025-01-10", "price_krw": price, "evidence_ids": [e["id"]]}]
    if repeated:
        events += [{"event_type": "resupply", "event_date": "2025-08-01", "price_krw": price, "evidence_ids": [e["id"]]}, {"event_type": "discretionary", "event_date": "2026-02-01", "price_krw": price, "evidence_ids": [e["id"]]}]
    # comparables.py drops any complex with fewer than 2 transactions (a single
    # outlier shouldn't stand in for a whole complex's price level), so the
    # synthetic "대표 구축" comparator needs at least 2 records to survive that filter.
    tx = [] if missing else [
        {"complex_name": "대표 구축", "area_m2": max((area or 59), 49), "price_krw": (price or 500_000_000) + 30_000_000, "year": year or 2015, "region": region, "households": 700, "evidence_ids": [e["id"]]},
        {"complex_name": "대표 구축", "area_m2": max((area or 59), 49), "price_krw": (price or 500_000_000) + 25_000_000, "year": year or 2015, "region": region, "households": 700, "evidence_ids": [e["id"]]},
    ]
    return {"property": {"name": name, "region": region, "address": region, "unit_type": "target", "exclusive_area_m2": area, "price_krw": price, "households": households, "completion_year": year, "property_type": "apartment", "commute_minutes": commute}, "evidence": [e], "sale_events": events, "transactions": tx, "new_supply": [], "alternatives": [], "location": {"nearest_station": "확인된 역", "walking_minutes": 10} if not missing else {}, "status": "partial" if missing else "ok"}
