from home_agent import daily_check


def _fake_notice(pblanc_no="p1", house_manage_no="h1"):
    return {
        "PBLANC_NO": pblanc_no,
        "HOUSE_MANAGE_NO": house_manage_no,
        "HOUSE_NM": "테스트 단지",
        "HSSPLY_ADRES": "경기도 의정부시 녹양동 일원",
        "TOT_SUPLY_HSHLDCO": 100,
        "PBLANC_URL": "https://example.com/notice",
        "RCEPT_BGNDE": "2026-09-01",
        "RCEPT_ENDDE": "2026-09-30",
    }


def _fake_model(model_no="01"):
    return {"HOUSE_TY": "059.9200A", "LTTOT_TOP_AMOUNT": "40000", "MODEL_NO": model_no}


def _fake_result(name):
    return {
        "schema_version": "1.0",
        "analysis_id": f"aid-{name}",
        "property_slug": f"slug-{name}",
        "verdict": {"status": "watch", "confidence": 0.1},
        "price_analysis": {"assessment": "fair"},
        "score": {"total": 50, "coverage_weight": 60},
        "missing_information": [],
    }


def test_run_analyzes_new_candidates_and_writes_digest(tmp_path, monkeypatch):
    notices = [_fake_notice()]
    models = [_fake_model()]

    monkeypatch.setattr(daily_check.applyhome, "fetch_open_notices", lambda as_of, regions, key: notices)
    monkeypatch.setattr(daily_check.applyhome, "fetch_house_models", lambda p, h, key: models)
    monkeypatch.setattr(daily_check, "analyze_property", lambda inp, **kw: _fake_result(inp["name"]))
    monkeypatch.setattr(daily_check.narrate, "narrate", lambda result, candidate, key: "요약 텍스트")

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    digest_path = daily_check.run(as_of="2026-09-11T00:00:00+00:00", config_dir=config_dir, data_dir=data_dir)

    assert digest_path.exists()
    content = digest_path.read_text(encoding="utf-8")
    assert "테스트 단지" in content
    assert "요약 텍스트" in content
    assert (data_dir / "seen_notices.json").exists()
    assert (data_dir / "reports" / "slug-테스트 단지" / "aid-테스트 단지.json").exists()


def test_run_skips_already_seen_candidates(tmp_path, monkeypatch):
    notices = [_fake_notice()]
    models = [_fake_model()]
    calls = {"n": 0}

    def fake_analyze(inp, **kw):
        calls["n"] += 1
        return _fake_result(inp["name"])

    monkeypatch.setattr(daily_check.applyhome, "fetch_open_notices", lambda as_of, regions, key: notices)
    monkeypatch.setattr(daily_check.applyhome, "fetch_house_models", lambda p, h, key: models)
    monkeypatch.setattr(daily_check, "analyze_property", fake_analyze)
    monkeypatch.setattr(daily_check.narrate, "narrate", lambda result, candidate, key: None)

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    daily_check.run(as_of="2026-09-11T00:00:00+00:00", config_dir=config_dir, data_dir=data_dir)
    daily_check.run(as_of="2026-09-11T00:00:00+00:00", config_dir=config_dir, data_dir=data_dir)

    assert calls["n"] == 1


def test_run_skips_candidates_missing_required_fields(tmp_path, monkeypatch):
    notices = [_fake_notice()]
    models = [{"HOUSE_TY": "", "LTTOT_TOP_AMOUNT": "", "MODEL_NO": "02"}]

    monkeypatch.setattr(daily_check.applyhome, "fetch_open_notices", lambda as_of, regions, key: notices)
    monkeypatch.setattr(daily_check.applyhome, "fetch_house_models", lambda p, h, key: models)
    called = []
    monkeypatch.setattr(daily_check, "analyze_property", lambda inp, **kw: called.append(inp) or _fake_result("x"))
    monkeypatch.setattr(daily_check.narrate, "narrate", lambda *a, **k: None)

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    daily_check.run(as_of="2026-09-11T00:00:00+00:00", config_dir=config_dir, data_dir=data_dir)

    assert called == []


def test_run_includes_notice_on_announcement_date_before_receipt(tmp_path, monkeypatch):
    notice = _fake_notice()
    notice.update({"RCRIT_PBLANC_DE": "2026-09-16", "RCEPT_BGNDE": "2026-09-18", "RCEPT_ENDDE": "2026-09-19"})
    monkeypatch.setattr(daily_check.applyhome, "fetch_open_notices", lambda *a: [notice])
    monkeypatch.setattr(daily_check.applyhome, "fetch_house_models", lambda *a: [_fake_model()])
    monkeypatch.setattr(daily_check, "analyze_property", lambda inp, **kw: _fake_result(inp["name"]))
    monkeypatch.setattr(daily_check.narrate, "narrate", lambda *a, **k: None)

    path = daily_check.run(as_of="2026-09-16T00:00:00+09:00", config_dir=tmp_path / "config", data_dir=tmp_path / "data")
    assert "오늘 신규 발표" in path.read_text(encoding="utf-8")
