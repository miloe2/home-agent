from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

import httpx

BASE_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1"
PAGE_SIZE = 100

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


def fetch_open_notices(as_of: str, regions: list[str], api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    key = unquote(api_key)
    today = as_of[:10]
    results: list[dict[str, Any]] = []
    for region in regions:
        page = 1
        while True:
            params = {
                "serviceKey": key,
                "page": page,
                "perPage": PAGE_SIZE,
                _cond("RCEPT_BGNDE", "LTE", today): today,
                _cond("RCEPT_ENDDE", "GTE", today): today,
                _cond("SUBSCRPT_AREA_CODE_NM", "EQ", region): region,
            }
            data = _http_get(f"{BASE_URL}/getAPTLttotPblancDetail", params)
            items = data.get("data") or []
            results.extend(items)
            if len(items) < PAGE_SIZE:
                break
            page += 1
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


def fetch_house_models(pblanc_no: str, house_manage_no: str, api_key: str) -> list[dict[str, Any]]:
    if not api_key:
        return []
    params = {
        "serviceKey": unquote(api_key),
        "page": 1,
        "perPage": PAGE_SIZE,
        _cond("HOUSE_MANAGE_NO", "EQ", house_manage_no): house_manage_no,
        _cond("PBLANC_NO", "EQ", pblanc_no): pblanc_no,
    }
    data = _http_get(f"{BASE_URL}/getAPTLttotPblancMdl", params)
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
        "name": notice.get("HOUSE_NM"),
        "region": _normalize_region(notice.get("HSSPLY_ADRES", "")),
        "unit_type": (model.get("HOUSE_TY") or "").strip(),
        "exclusive_area_m2": area,
        "price_krw": price,
        "households": households if isinstance(households, int) and households > 0 else None,
        "new_build": True,
        "expected_move_in_ym": _normalize_move_in_ym(notice.get("MVN_PREARNGE_YM")),
        "pblanc_no": notice.get("PBLANC_NO"),
        "house_manage_no": notice.get("HOUSE_MANAGE_NO"),
        "model_no": model.get("MODEL_NO"),
        "official_url": notice.get("PBLANC_URL"),
        "rcept_bgnde": notice.get("RCEPT_BGNDE"),
        "rcept_endde": notice.get("RCEPT_ENDDE"),
    }
