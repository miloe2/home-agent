"""Stage [1] of the analysis pipeline: source facts collection.

Returns the property + whatever transactions/history/location data the
configured source (mock fixture or live MOLIT) can provide, as an unfiltered
pool. This stage does not judge "same area" vs "larger area" or compute any
price comparison - that's comparables.py's job (stage [2]). Keeping the area
tolerance filter out of this stage means facts.py only ever answers "what did
the source return", never "what's comparable to the target".
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import molit
from .core import load_yaml
from .mock import build_case as _build_mock_case


def collect_facts(inp: dict[str, Any], mode: str, config_path: Path, as_of: str | None) -> dict[str, Any]:
    if mode == "mock":
        return _build_mock_case(inp)
    return _collect_live_facts(inp, config_path, as_of)


def _collect_live_facts(inp: dict[str, Any], config_path: Path, as_of: str | None) -> dict[str, Any]:
    region_table = load_yaml(config_path / "region_codes.yaml").get("codes", {})
    api_key = os.environ.get("HOME_AGENT_MOLIT_API_KEY", "")
    region = inp.get("region")
    result = molit.fetch_transactions_live(region, as_of, api_key, region_table)
    tx = result["transactions"]
    warnings = []
    if result["status"] != "ok":
        warnings.append(f"국토부 실거래가 조회 불가: {result.get('reason') or result['status']}")
    elif not tx:
        warnings.append("조회된 실거래 자료가 없습니다.")
    return {
        "property": dict(inp),
        "evidence": result["evidence"],
        "sale_events": [],
        "transactions": tx,  # unfiltered pool; comparables.py applies the area tolerance
        "new_supply": [],
        "alternatives": [],
        "location": {},
        "status": "ok" if tx else ("partial" if result["status"] == "ok" else result["status"]),
        "warnings": warnings,
        "search_scope": {"months_queried": result["months_queried"], "extended_lookback": result["extended_lookback"]},
    }
