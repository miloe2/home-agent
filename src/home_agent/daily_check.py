from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from . import applyhome, narrate, seen_store
from .analyze import analyze_property
from .core import kst_date, utc_now
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
    return f"{candidate.get('pblanc_no')}:{candidate.get('supply_type', 'APT')}:{candidate.get('model_no')}"


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

    today = kst_date(as_of)
    notices = applyhome.fetch_open_notices(as_of, TARGET_REGIONS, molit_key)
    digest: list[dict[str, Any]] = []
    notice_seen: set[tuple[str, str]] = set()

    for notice in notices:
        pblanc_no = notice.get("PBLANC_NO")
        house_manage_no = notice.get("HOUSE_MANAGE_NO")
        if not pblanc_no or not house_manage_no:
            continue
        supply_type = notice.get("supply_type", "APT")
        notice_identity = (str(pblanc_no), supply_type)
        if notice_identity in notice_seen:
            continue
        notice_seen.add(notice_identity)
        if supply_type == "APT":
            # Keep the old three-argument call usable for integrations that
            # monkeypatch or wrap the original public function.
            models = applyhome.fetch_house_models(pblanc_no, house_manage_no, molit_key)
        else:
            models = applyhome.fetch_house_models(pblanc_no, house_manage_no, molit_key, supply_type)
        for model in models:
            candidate = applyhome.normalize_candidate(notice, model)
            if candidate is None:
                continue
            key = _seen_key(candidate)
            legacy_key = f"{candidate['pblanc_no']}:{candidate['model_no']}"
            first_detected = not seen_store.is_seen(seen, key) and not seen_store.is_seen(seen, legacy_key)
            newly_announced = candidate.get("announcement_date") == today
            currently_open = bool(candidate.get("rcept_bgnde") and candidate.get("rcept_endde") and candidate["rcept_bgnde"] <= today <= candidate["rcept_endde"])
            if not first_detected:
                # Keep the daily report useful for a long-running watcher even
                # after analysis has already been persisted.
                digest.append({"candidate": candidate, "result": None, "narrative": None,
                               "newly_announced": newly_announced, "currently_open": currently_open,
                               "first_detected": False})
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
            digest.append({"candidate": candidate, "result": result, "narrative": summary,
                           "newly_announced": newly_announced, "currently_open": currently_open,
                           "first_detected": True})

    digest_path = _write_digest(data_dir, as_of, digest)
    print(f"scanned {len(notices)} notices, {len(digest)} new candidates analyzed")
    print(f"digest: {digest_path}")
    return digest_path


def _write_digest(data_dir: Path, as_of: str, digest: list[dict[str, Any]]) -> Path:
    folder = data_dir / "reports" / "_daily"
    folder.mkdir(parents=True, exist_ok=True)
    date_str = kst_date(as_of)
    path = folder / f"{date_str}.md"
    new_count = sum(1 for item in digest if item.get("newly_announced"))
    open_count = sum(1 for item in digest if item.get("currently_open"))
    first_count = sum(1 for item in digest if item.get("first_detected"))
    lines = [f"# 일일 신규 공고 스캔 ({date_str})", "", f"신규 후보 {first_count}건", f"신규 발표 {new_count}건 / 현재 접수 중 {open_count}건 / 최초 감지 {first_count}건", ""]
    for item in digest:
        c, r = item["candidate"], item["result"]
        labels = []
        if item.get("newly_announced"): labels.append("오늘 신규 발표")
        if item.get("currently_open"): labels.append("현재 접수 중")
        if item.get("first_detected"): labels.append("최초 감지")
        lines += [
            f"## {c['name']} ({c['unit_type']})",
            f"- 공급유형: {c.get('supply_type', 'APT')} / 상태: {', '.join(labels) or '기존 공고'}",
            f"- 지역: {c['region']}",
            f"- 전용면적: {c['exclusive_area_m2']}㎡ / 가격: {c['price_krw']}원",
            f"- 접수기간: {c['rcept_bgnde']} ~ {c['rcept_endde']}",
        ]
        if r:
            v = r["verdict"]
            lines += [f"- verdict: {v['status']} (confidence={v['confidence']})",
                      f"- 공식 공고: {c['official_url']}",
                      f"- 상세 리포트: data/reports/{r['property_slug']}/{r['analysis_id']}.json"]
        else:
            lines.append("- 분석 리포트: 기존 분석 결과는 이미 저장됨")
        if item["narrative"]:
            lines += ["", item["narrative"]]
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


if __name__ == "__main__":
    run()
