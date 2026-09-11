from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .analyze import analyze_property
from .core import load_yaml
from .storage import ReportStore

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without printing or overriding shell values."""
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


_load_dotenv(ROOT / ".env")
CONFIG = Path(os.getenv("HOME_AGENT_CONFIG_DIR", ROOT / "config"))
DATA = Path(os.getenv("HOME_AGENT_DATA_DIR", ROOT / "data"))
MODE = os.getenv("HOME_AGENT_SOURCE_MODE", "mock")
store = ReportStore(DATA / "reports")

class PropertyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    unit_type: str = Field(min_length=1, max_length=40)
    region: str | None = None
    address: str | None = None
    exclusive_area_m2: float | None = Field(default=None, gt=0)
    price_krw: int | None = Field(default=None, gt=0)
    official_property_id: str | None = None
    sale_notice_id: str | None = None
    property_type: str | None = None
    @field_validator("name", "unit_type")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()

app = FastAPI(title="Home Agent", version="0.1.0")

@app.get("/health")
def health(): return {"status": "ok", "mode": MODE, "schema_version": "1.0"}

@app.get("/profile")
def profile(): return load_yaml(CONFIG / "user_profile.yaml")

@app.post("/profile/validate")
def validate_profile(payload: dict):
    errors = []
    budget = payload.get("budget", {})
    if budget.get("preferred_max_price_krw", 0) > budget.get("stretch_max_price_krw", 0): errors.append("preferred_max_price_krw must not exceed stretch_max_price_krw")
    return {"valid": not errors, "errors": errors, "normalized_profile": payload if not errors else None}

@app.post("/analyze")
def analyze(req: PropertyInput):
    try:
        result = analyze_property(req.model_dump(exclude_none=True), config_dir=str(CONFIG), mode=MODE)
        store.save(result)
        return result
    except ValueError as e: raise HTTPException(422, detail={"code": "invalid_input", "message": str(e)}) from e
    except Exception as e: raise HTTPException(500, detail={"code": "analysis_failed", "message": str(e)}) from e

@app.get("/reports/{property_slug}")
def report(property_slug: str):
    try: result = store.latest(property_slug)
    except ValueError as e: raise HTTPException(422, detail={"code": "invalid_slug", "message": str(e)}) from e
    if result is None: raise HTTPException(404, detail={"code": "report_not_found", "message": "report not found"})
    return result
