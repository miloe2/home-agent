from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

import httpx
from defusedxml import ElementTree as ET

from .core import evidence

BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
NUM_ROWS = 1000


def resolve_lawd_cd(region: str | None, table: dict[str, str]) -> str | None:
    """Resolve a free-text address to a LAWD_CD.

    Multi-district project addresses (e.g. "인천광역시 계양구 ... 및 경기도 부천시 ...
    서울특별시 강서구 ... 일원") legitimately mention several jurisdictions; the
    project's actual site is always the one named first. We therefore pick the
    matching key whose first token appears earliest in the string, not merely
    the key with the most tokens - a token-count tiebreak alone previously let
    a later-listed, unrelated district win by config file ordering.
    """
    if not region:
        return None
    norm = " ".join(region.split())
    if norm in table:
        return table[norm]
    candidates = []
    for key, code in table.items():
        tokens = key.split()
        positions = [norm.find(t) for t in tokens]
        if any(p == -1 for p in positions):
            continue
        candidates.append((min(positions), -len(tokens), code))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def _http_get(url: str, params: dict[str, Any]) -> str:
    with httpx.Client(timeout=httpx.Timeout(connect=5, read=15, write=15, pool=15)) as client:
        resp = client.get(url, params=params)
        # data.go.kr returns a structured XML error body (e.g. SERVICE_KEY_IS_NOT_REGISTERED_ERROR)
        # even on 4xx/5xx status, so the body is parsed instead of raising here.
        return resp.text


def _parse_response(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    auth_err = root.findtext(".//cmmMsgHeader/returnAuthMsg") or root.findtext(".//cmmMsgHeader/errMsg")
    if auth_err:
        return {"status": "unavailable", "reason": auth_err, "items": [], "total_count": 0}
    result_code = root.findtext(".//resultCode")
    if result_code is not None and result_code.strip() not in {"00", "000"}:
        reason = root.findtext(".//resultMsg") or "unknown_error"
        return {"status": "unavailable", "reason": reason, "items": [], "total_count": 0}
    total_count = int((root.findtext(".//totalCount") or "0").strip() or 0)
    items = [{child.tag: (child.text or "").strip() for child in item} for item in root.findall(".//items/item")]
    return {"status": "ok", "items": items, "total_count": total_count}


def _normalize_item(raw: dict[str, str], region: str) -> dict[str, Any] | None:
    if (raw.get("cdealType") or "").strip():
        return None
    amount = (raw.get("dealAmount") or "").replace(",", "").strip()
    if not amount.isdigit():
        return None
    try:
        area = float(raw["excluUseAr"]) if raw.get("excluUseAr") else None
    except ValueError:
        area = None
    build_year = raw.get("buildYear")
    year = int(build_year) if build_year and build_year.isdigit() else None
    return {
        "complex_name": raw.get("aptNm") or "확인된 단지",
        "area_m2": area,
        "price_krw": int(amount) * 10_000,
        "year": year,
        "region": raw.get("umdNm") or region,
        "households": None,
    }


def _fetch_month(lawd_cd: str, year_month: str, api_key: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    items: list[dict[str, Any]] = []
    ev: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {"serviceKey": api_key, "LAWD_CD": lawd_cd, "DEAL_YMD": year_month, "pageNo": page, "numOfRows": NUM_ROWS}
        safe_query = "&".join(f"{k}={v}" for k, v in params.items() if k != "serviceKey")
        try:
            text = _http_get(BASE_URL, params)
            parsed = _parse_response(text)
        except httpx.HTTPError as e:
            status = {"status": "unavailable", "reason": str(e), "items": [], "total_count": 0}
            ev.append(evidence(f"{BASE_URL}?{safe_query}", source_type="official_api", adapter="molit", mock=False, excerpt=str(e)))
            return items, ev, status
        except ET.ParseError as e:
            status = {"status": "unavailable", "reason": f"invalid_response_format: {e}", "items": [], "total_count": 0}
            ev.append(evidence(f"{BASE_URL}?{safe_query}", source_type="official_api", adapter="molit", mock=False, excerpt=str(e)))
            return items, ev, status
        ev.append(evidence(f"{BASE_URL}?{safe_query}", source_type="official_api", adapter="molit", mock=False, excerpt=parsed.get("reason", "")))
        if parsed["status"] != "ok":
            return items, ev, parsed
        items.extend(parsed["items"])
        if len(items) >= parsed["total_count"] or not parsed["items"]:
            return items, ev, parsed
        page += 1


def _prev_month(dt: datetime) -> datetime:
    year, month = dt.year, dt.month - 1
    if month == 0:
        year, month = year - 1, 12
    return dt.replace(year=year, month=month, day=1)


def fetch_transactions_live(
    region: str | None,
    as_of: str | None,
    api_key: str | None,
    region_table: dict[str, str],
    *,
    months: int = 12,
    max_months: int = 24,
) -> dict[str, Any]:
    lawd_cd = resolve_lawd_cd(region, region_table)
    if not lawd_cd:
        return {"status": "unavailable", "reason": "지역코드 매핑 실패", "transactions": [], "evidence": [], "months_queried": 0, "extended_lookback": False}
    if not api_key:
        return {"status": "unavailable", "reason": "MOLIT API 키 없음", "transactions": [], "evidence": [], "months_queried": 0, "extended_lookback": False}
    key = unquote(api_key)
    cursor = datetime.fromisoformat(as_of) if as_of else datetime.now(UTC)
    cursor = cursor.replace(day=1)
    all_tx: list[dict[str, Any]] = []
    all_ev: list[dict[str, Any]] = []
    limit = months
    queried = 0
    last_status = "ok"
    last_reason = None
    while queried < max_months:
        year_month = f"{cursor.year:04d}{cursor.month:02d}"
        items, ev, month_status = _fetch_month(lawd_cd, year_month, key)
        all_ev.extend(ev)
        for raw in items:
            norm = _normalize_item(raw, region or "")
            if norm:
                all_tx.append(norm)
        queried += 1
        last_status = month_status["status"]
        last_reason = month_status.get("reason")
        if last_status != "ok":
            break
        cursor = _prev_month(cursor)
        if queried >= limit:
            if len(all_tx) >= 3 or limit >= max_months:
                break
            limit = max_months
    if not all_tx:
        status = last_status if last_status != "ok" else "insufficient_information"
        reason = last_reason if last_status != "ok" else None
    else:
        status = "ok"
        reason = None
    return {
        "status": status,
        "reason": reason,
        "transactions": all_tx,
        "evidence": all_ev,
        "months_queried": queried,
        "extended_lookback": queried > months,
    }
