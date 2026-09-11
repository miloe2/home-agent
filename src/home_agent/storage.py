from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ReportStore:
    def __init__(self, root: str | Path = "data/reports"):
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
    def save(self, result: dict[str, Any]) -> Path:
        slug = result["property_slug"]
        if ".." in slug or "/" in slug or "\\" in slug: raise ValueError("invalid slug")
        folder = (self.root / slug).resolve()
        if self.root not in folder.parents: raise ValueError("invalid path")
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{result['analysis_id']}.json"; tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); os.replace(tmp, target)
        return target
    def latest(self, slug: str) -> dict[str, Any] | None:
        if ".." in slug or "/" in slug or "\\" in slug: raise ValueError("invalid slug")
        folder = (self.root / slug).resolve()
        if self.root not in folder.parents or not folder.exists(): return None
        files = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in files:
            try: return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError: continue
        return None
