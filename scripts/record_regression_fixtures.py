"""One-time recorder: freeze the 8 regression cases (source facts) to disk.

Run manually (needs live MOLIT_API_KEY): `python scripts/record_regression_fixtures.py`

This captures, per case:
- the PropertyInput derived from a real 청약홈 notice/model (via applyhome)
- the exact `molit.fetch_transactions_live()` result for that property's region

so tests/test_regression_cases.py can replay `analyze_property(mode="live")`
offline by monkeypatching `molit.fetch_transactions_live`, without depending
on live MOLIT data changing day to day.
"""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path

import yaml

from home_agent import applyhome, daily_check, molit

daily_check._load_dotenv(daily_check.ROOT / ".env")

KEY = os.environ["HOME_AGENT_MOLIT_API_KEY"]
AS_OF = "2026-09-11T00:00:00+00:00"

CASES = [
    ("yangju_hoecheon_59", "양주회천지구 A-26", "059.7400A"),
    ("uijeongbu_ujeong_59", "의정부우정", "059.9200A"),
    ("incheon_gyeyang_59", "인천계양지구 A6", "059.8400A"),
    ("incheon_gyeyang_69", "인천계양지구 A6", "069.8200P"),
    ("namyangju_wangsuk_59", "남양주왕숙2", "059.0000A"),
    ("namyangju_wangsuk_74", "남양주왕숙2", "074.0000A"),
    ("namyangju_wangsuk_84", "남양주왕숙2", "084.0000A"),
    ("seongnam_bokjeong_55", "성남복정2", "055.9700A"),
]

OUT_DIR = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "regression"
OUT_DIR.mkdir(parents=True, exist_ok=True)
with open(Path(__file__).resolve().parents[1] / "config" / "region_codes.yaml", encoding="utf-8") as f:
    region_table = yaml.safe_load(f)["codes"]

for fixture_name, query, unit_type in CASES:
    notice = applyhome.search_notices(query, KEY)[0]
    models = applyhome.fetch_house_models(notice["PBLANC_NO"], notice["HOUSE_MANAGE_NO"], KEY)
    model = next(m for m in models if m["HOUSE_TY"].strip() == unit_type)
    candidate = applyhome.normalize_candidate(notice, model)
    property_input = {k: v for k, v in candidate.items() if k in daily_check.PROPERTY_INPUT_FIELDS and v is not None}

    molit_result = molit.fetch_transactions_live(property_input["region"], AS_OF, KEY, region_table)
    molit_result = {**molit_result, "evidence": []}  # evidence timestamps aren't needed for regression assertions

    fixture = {"property_input": property_input, "as_of": AS_OF, "molit_result": molit_result}
    path = OUT_DIR / f"{fixture_name}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False)
    print(f"wrote {path} ({len(molit_result['transactions'])} transactions)")
