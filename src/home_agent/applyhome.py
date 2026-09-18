from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote

import httpx

BASE_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
PAGE_SIZE = 100

SUPPLY_ENDPOINTS = {
    "APT": ("getAPTLttotPblancDetail", "getAPTLttotPblancMdl"),
    "REMNANT": ("getRemndrLttotPblancDetail", "getRemndrLttotPblancMdl"),
    "OPTIONAL": ("getOPTLttotPblancDetail", "getOPTLttotPblancMdl"),
}

_AREA_RE = re.compile(r"[\d.]+")
_SIDO_MAP = {"서울특별시": "서울", "경기도": "경기", "인천광역시": "인천"}


def _http_get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=httpx.Timeout(connect=5, read=15, write=15, pool=15)) as client:
        resp = client.get(url, params=params)
        try:
            return resp.json()
        except ValueError:
            return {"error": f"non-json response: {resp.status_code}"}


def _cond(field: str, op: str, value: str) -> str:
    return f"cond[{field}::{op}]"


def _first(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def _notice_dates(row: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (
        _first(row, "RCRIT_PBLANC_DE", "PBLANC_DE"),
        _first(row, "RCEPT_BGNDE", "SUBSCRPT_RCEPT_BGNDE", "GNRL_RCEPT_BGNDE"),
        _first(row, "RCEPT_ENDDE", "SUBSCRPT_RCEPT_ENDDE", "GNRL_RCEPT_ENDDE"),
    )


def normalize_notice(notice: dict[str, Any], supply_type: str) -> dict[str, Any]:
    """Add stable names while retaining every original 청약Home field."""
    announcement, receipt_start, receipt_end = _notice_dates(notice)
    out = dict(notice)
    out.update({
        "supply_type": supply_type,
        "pblanc_no": _first(notice, "PBLANC_NO"),
        "house_nm": _first(notice, "HOUSE_NM"),
        "address": _first(notice, "HSSPLY_ADRES", "HSSPLY_ADDR"),
        "announcement_date": announcement,
        "receipt_start_date": receipt_start,
        "receipt_end_date": receipt_end,
        "homepage_url": _first(notice, "PBLANC_URL", "HMPG_ADRES"),
    })
    return out


def _date_in_scope(notice: dict[str, Any], today: str) -> bool:
    announcement, start, end = _notice_dates(notice)
    # Preserve compatibility with partial/legacy records. Real 청약Home
    # records have at least the announcement or receipt dates.
    if not announcement and not start and not end:
        return True
    return announcement == today or bool(start and end and start <= today <= end)


def _fetch_endpoint(endpoint: str, today: str, region: str, key: str, *, mode: str, supply_type: str) -> list[dict[str, Any]]:
    page = 1
    result = []
    while True:
        params = {
            "serviceKey": key, "page": page, "perPage": PAGE_SIZE,
            _cond("SUBSCRPT_AREA_CODE_NM", "EQ", region): region,
        }
        if mode == "new":
            params[_cond("RCRIT_PBLANC_DE", "EQ", today)] = today
        else:
            # These are the common fields used by the APT/OPT feeds. Remnant
            # feeds use SUBSCRPT_RCEPT_*; local filtering below handles both.
            if supply_type == "REMNANT":
                start_field, end_field = "SUBSCRPT_RCEPT_BGNDE", "SUBSCRPT_RCEPT_ENDDE"
            else:
                start_field, end_field = "RCEPT_BGNDE", "RCEPT_ENDDE"
            params[_cond(start_field, "LTE", today)] = today
            params[_cond(end_field, "GTE", today)] = today
        data = _http_get(f"{BASE_URL}/{endpoint}", params)
        items = data.get("data") or []
        result.extend(items)
        if len(items) < PAGE_SIZE:
            break
        page += 1
    return result


def fetch_open_notices(as_of: str, regions: list[str], api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    key = unquote(api_key)
    from .core import kst_date

    today = kst_date(as_of)
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for region in regions:
        for supply_type, (detail_endpoint, _) in SUPPLY_ENDPOINTS.items():
            # Two views are intentional: newly published notices are visible
            # before their receipt window starts, while active notices may be
            # much older than today.
            items = _fetch_endpoint(detail_endpoint, today, region, key, mode="new", supply_type=supply_type)
            items += _fetch_endpoint(detail_endpoint, today, region, key, mode="active", supply_type=supply_type)
            for raw in items:
                notice = normalize_notice(raw, supply_type)
                if not _date_in_scope(notice, today):
                    continue
                pblanc = str(notice.get("pblanc_no") or "")
                if not pblanc:
                    continue
                # Some mocked/legacy feeds return the exact same object for
                # every endpoint. Avoid manufacturing three copies there.
                raw_fingerprint = json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str)
                identity = (pblanc, supply_type)
                if identity in seen or ("__identical__", raw_fingerprint) in seen:
                    continue
                seen.add(identity)
                seen.add(("__identical__", raw_fingerprint))
                results.append(notice)
    return results


def search_notices(name: str, api_key: str, *, limit: int = 20) -> list[dict[str, Any]]:
    if not api_key or not name:
        return []
    params = {
        "serviceKey": unquote(api_key),
        "page": 1,
        "perPage": limit,
        _cond("HOUSE_NM", "LIKE", name): name,
    }
    data = _http_get(f"{BASE_URL}/getAPTLttotPblancDetail", params)
    return data.get("data") or []


def fetch_house_models(pblanc_no: str, house_manage_no: str, api_key: str, supply_type: str = "APT") -> list[dict[str, Any]]:
    if not api_key:
        return []
    params = {
        "serviceKey": unquote(api_key),
        "page": 1,
        "perPage": PAGE_SIZE,
        _cond("HOUSE_MANAGE_NO", "EQ", house_manage_no): house_manage_no,
        _cond("PBLANC_NO", "EQ", pblanc_no): pblanc_no,
    }
    _, model_endpoint = SUPPLY_ENDPOINTS.get(supply_type, SUPPLY_ENDPOINTS["APT"])
    data = _http_get(f"{BASE_URL}/{model_endpoint}", params)
    return data.get("data") or []


def _parse_area(house_ty: str) -> float | None:
    m = _AREA_RE.search(house_ty or "")
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def _normalize_region(address: str) -> str:
    addr = (address or "").strip()
    for full, short in _SIDO_MAP.items():
        if addr.startswith(full):
            return short + " " + addr[len(full):].strip()
    return addr


def _normalize_move_in_ym(raw: str | None) -> str | None:
    raw = (raw or "").strip()
    if len(raw) != 6 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:]}"


def normalize_candidate(notice: dict[str, Any], model: dict[str, Any]) -> dict[str, Any] | None:
    area = _parse_area(model.get("HOUSE_TY", ""))
    amount = (model.get("LTTOT_TOP_AMOUNT") or "").strip()
    price = int(amount) * 10_000 if amount.isdigit() else None
    households = notice.get("TOT_SUPLY_HSHLDCO")
    return {
        "name": notice.get("HOUSE_NM") or notice.get("house_nm"),
        "region": _normalize_region(notice.get("HSSPLY_ADRES") or notice.get("address", "")),
        "address": notice.get("HSSPLY_ADRES") or notice.get("address"),
        "supply_type": notice.get("supply_type", "APT"),
        "unit_type": (model.get("HOUSE_TY") or "").strip(),
        "exclusive_area_m2": area,
        "price_krw": price,
        "households": households if isinstance(households, int) and households > 0 else None,
        "new_build": True,
        "expected_move_in_ym": _normalize_move_in_ym(notice.get("MVN_PREARNGE_YM")),
        "pblanc_no": notice.get("PBLANC_NO"),
        "house_manage_no": notice.get("HOUSE_MANAGE_NO"),
        "model_no": model.get("MODEL_NO"),
        "official_url": notice.get("PBLANC_URL") or notice.get("homepage_url"),
        "rcept_bgnde": notice.get("RCEPT_BGNDE") or notice.get("receipt_start_date"),
        "rcept_endde": notice.get("RCEPT_ENDDE") or notice.get("receipt_end_date"),
        "announcement_date": notice.get("announcement_date") or notice.get("RCRIT_PBLANC_DE"),
    }
