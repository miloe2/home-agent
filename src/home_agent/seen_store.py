from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .core import utc_now


def load(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def is_seen(store: dict[str, Any], key: str) -> bool:
    return key in store


def mark_seen(path: str | Path, store: dict[str, Any], key: str, analysis_id: str) -> dict[str, Any]:
    store[key] = {"first_seen": utc_now(), "analysis_id": analysis_id}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return store
