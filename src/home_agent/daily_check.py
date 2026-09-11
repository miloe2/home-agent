from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from . import applyhome, narrate, seen_store
from .analyze import analyze_property
from .core import utc_now
from .storage import ReportStore

ROOT = Path(__file__).resolve().parents[2]
TARGET_REGIONS = ["서울", "경기"]
PROPERTY_INPUT_FIELDS = {"name", "region", "unit_type", "exclusive_area_m2", "price_krw", "households", "new_build", "expected_move_in_ym"}


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key:
            os.environ.setdefault(key, value)


def _seen_key(candidate: dict[str, Any]) -> str:
    return f"{candidate['pblanc_no']}:{candidate['model_no']}"


def run(as_of: str | None = None, config_dir: str | Path = "config", data_dir: str | Path = "data") -> Path:
    _load_dotenv(ROOT / ".env")
    config_dir = Path(config_dir)
    data_dir = Path(data_dir)
    as_of = as_of or utc_now()
    molit_key = os.environ.get("HOME_AGENT_MOLIT_API_KEY", "")
    gemini_key = os.environ.get("HOME_AGENT_GEMINI_API_KEY")

    seen_path = data_dir / "seen_notices.json"
    seen = seen_store.load(seen_path)
    store = ReportStore(data_dir / "reports")

    notices = applyhome.fetch_open_notices(as_of, TARGET_REGIONS, molit_key)
    digest: list[dict[str, Any]] = []

    for notice in notices:
        pblanc_no = notice.get("PBLANC_NO")
        house_manage_no = notice.get("HOUSE_MANAGE_NO")
        if not pblanc_no or not house_manage_no:
            continue
        models = applyhome.fetch_house_models(pblanc_no, house_manage_no, molit_key)
        for model in models:
            candidate = applyhome.normalize_candidate(notice, model)
            if candidate is None:
                continue
            key = _seen_key(candidate)
            if seen_store.is_seen(seen, key):
                continue
            property_input = {k: v for k, v in candidate.items() if k in PROPERTY_INPUT_FIELDS and v is not None}
            if not property_input.get("name") or not property_input.get("unit_type"):
                continue
            result = analyze_property(property_input, config_dir=str(config_dir), as_of=as_of, mode="live")
            store.save(result)
            if digest and gemini_key:
                time.sleep(6)  # stay under free-tier requests-per-minute limits
            summary = narrate.narrate(result, candidate, gemini_key)
            seen = seen_store.mark_seen(seen_path, seen, key, result["analysis_id"])
            digest.append({"candidate": candidate, "result": result, "narrative": summary})

    digest_path = _write_digest(data_dir, as_of, digest)
    print(f"scanned {len(notices)} notices, {len(digest)} new candidates analyzed")
    print(f"digest: {digest_path}")
    return digest_path


def _write_digest(data_dir: Path, as_of: str, digest: list[dict[str, Any]]) -> Path:
    folder = data_dir / "reports" / "_daily"
    folder.mkdir(parents=True, exist_ok=True)
    date_str = as_of[:10]
    path = folder / f"{date_str}.md"
    lines = [f"# 일일 신규 공고 스캔 ({date_str})", "", f"신규 후보 {len(digest)}건", ""]
    for item in digest:
        c, r = item["candidate"], item["result"]
        v = r["verdict"]
        lines += [
            f"## {c['name']} ({c['unit_type']})",
            f"- 지역: {c['region']}",
            f"- 전용면적: {c['exclusive_area_m2']}㎡ / 가격: {c['price_krw']}원",
            f"- 접수기간: {c['rcept_bgnde']} ~ {c['rcept_endde']}",
            f"- verdict: {v['status']} (confidence={v['confidence']})",
            f"- 공식 공고: {c['official_url']}",
            f"- 상세 리포트: data/reports/{r['property_slug']}/{r['analysis_id']}.json",
        ]
        if item["narrative"]:
            lines += ["", item["narrative"]]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    run()
