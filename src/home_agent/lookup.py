from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from . import applyhome, narrate
from .analyze import analyze_property
from .daily_check import PROPERTY_INPUT_FIELDS, ROOT, _load_dotenv


def run(query: str, config_dir: str | Path = "config") -> list[dict[str, Any]]:
    _load_dotenv(ROOT / ".env")
    key = os.environ.get("HOME_AGENT_MOLIT_API_KEY", "")
    gemini_key = os.environ.get("HOME_AGENT_GEMINI_API_KEY")
    notices = applyhome.search_notices(query, key)
    if not notices:
        print(f"'{query}'로 검색된 공고가 없습니다.")
        return []

    all_results = []
    for notice in notices:
        print(f"=== {notice.get('HOUSE_NM')} ({notice.get('HOUSE_MANAGE_NO')}) "
              f"지역:{notice.get('SUBSCRPT_AREA_CODE_NM')} "
              f"접수:{notice.get('RCEPT_BGNDE')}~{notice.get('RCEPT_ENDDE')} ===")
        pblanc_no = notice.get("PBLANC_NO")
        house_manage_no = notice.get("HOUSE_MANAGE_NO")
        if not pblanc_no or not house_manage_no:
            continue
        models = applyhome.fetch_house_models(pblanc_no, house_manage_no, key)
        for model in models:
            candidate = applyhome.normalize_candidate(notice, model)
            if candidate is None:
                continue
            inp = {k: v for k, v in candidate.items() if k in PROPERTY_INPUT_FIELDS and v is not None}
            if not inp.get("name") or not inp.get("unit_type"):
                continue
            result = analyze_property(inp, config_dir=str(config_dir), mode="live")
            price = result["price_analysis"]
            print(
                f"  {candidate['unit_type']} {candidate['exclusive_area_m2']}㎡ "
                f"{candidate['price_krw']:,}원 -> verdict={result['verdict']['status']} "
                f"price={price['assessment']} ratio={price['ratio_to_reference']} "
                f"score={result['score']['total']}"
            )
            if all_results and gemini_key:
                time.sleep(6)  # stay under free-tier requests-per-minute limits
            summary = narrate.narrate(result, candidate, gemini_key)
            if summary:
                print(f"  --- Gemini ---\n  {summary}\n")
            all_results.append(result)
    return all_results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python -m home_agent.lookup <house name>")
    run(sys.argv[1])
