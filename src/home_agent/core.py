from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - production installs PyYAML
    yaml = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def kst_now() -> datetime:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Asia/Seoul"))


def kst_date(as_of: str | datetime | None = None) -> str:
    """Return the scanner date in Korea, converting an aware input first."""
    from zoneinfo import ZoneInfo

    value = datetime.now(UTC) if as_of is None else as_of
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to load configuration")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def slug_for(data: dict[str, Any]) -> str:
    name = re.sub(r"[^0-9A-Za-z가-힣]+", "-", data.get("name", "property")).strip("-")[:40] or "property"
    identity = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{name.lower()}-{hashlib.sha256(identity.encode()).hexdigest()[:16]}"


def evidence(source_url: str, source_type: str = "mock", adapter: str = "mock", *, mock: bool = True, excerpt: str = "") -> dict[str, Any]:
    return {"id": f"E{uuid.uuid4().hex[:8].upper()}", "source_url": source_url,
            "fetched_at": utc_now(), "source_type": source_type, "adapter": adapter,
            "is_mock": mock, "excerpt": excerpt}


def fact(value: Any, evidence_ids: list[str], status: str = "known") -> dict[str, Any]:
    return {"value": value, "status": status, "evidence_ids": evidence_ids}


def finding(code: str, kind: str, text: str, *, severity: str = "info", evidence_ids: list[str] | None = None, rule_id: str | None = None) -> dict[str, Any]:
    return {"code": code, "kind": kind, "text": text, "severity": severity,
            "evidence_ids": evidence_ids or [], "rule_id": rule_id}


def clean_input(value: dict[str, Any]) -> dict[str, Any]:
    allowed = {"name", "region", "address", "unit_type", "exclusive_area_m2", "price_krw", "official_property_id", "sale_notice_id", "property_type", "households", "new_build", "expected_move_in_ym"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unknown fields: {sorted(unknown)}")
    out = dict(value)
    for key in ("name", "unit_type"):
        if not isinstance(out.get(key), str) or not out[key].strip():
            raise ValueError(f"{key} is required")
        out[key] = out[key].strip()
    if "price_krw" in out and (isinstance(out["price_krw"], bool) or not isinstance(out["price_krw"], int) or out["price_krw"] <= 0):
        raise ValueError("price_krw must be a positive integer")
    if "exclusive_area_m2" in out and (isinstance(out["exclusive_area_m2"], bool) or not isinstance(out["exclusive_area_m2"], (int, float)) or out["exclusive_area_m2"] <= 0):
        raise ValueError("exclusive_area_m2 must be positive")
    if "households" in out and (isinstance(out["households"], bool) or not isinstance(out["households"], int) or out["households"] <= 0):
        raise ValueError("households must be a positive integer")
    if "new_build" in out and not isinstance(out["new_build"], bool):
        raise ValueError("new_build must be a boolean")
    return out


def deep_get(obj: dict[str, Any], path: str, default: Any = None) -> Any:
    for part in path.split("."):
        if not isinstance(obj, dict): return default
        obj = obj.get(part, default)
    return obj
