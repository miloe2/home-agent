import json
from pathlib import Path

from home_agent import applyhome
from home_agent.core import kst_date


def test_parse_area_variants():
    assert applyhome._parse_area("059.9935B") == 59.9935
    assert applyhome._parse_area("054.8244 ") == 54.8244
    assert applyhome._parse_area("") is None
    assert applyhome._parse_area(None) is None


def test_normalize_region_strips_sido_suffix():
    assert applyhome._normalize_region("경기도 남양주시 오남읍 양지리 186-10번지 일원") == "경기 남양주시 오남읍 양지리 186-10번지 일원"
    assert applyhome._normalize_region("서울특별시 구로구 개봉동") == "서울 구로구 개봉동"
    assert applyhome._normalize_region("") == ""


def test_normalize_candidate_converts_price_to_won():
    notice = {
        "HOUSE_NM": "테스트 단지",
        "HSSPLY_ADRES": "경기도 의정부시 녹양동 일원",
        "TOT_SUPLY_HSHLDCO": 463,
        "PBLANC_NO": "0000061159",
        "HOUSE_MANAGE_NO": "0000061159",
        "PBLANC_URL": "https://example.com",
        "RCEPT_BGNDE": "2026-09-16",
        "RCEPT_ENDDE": "2026-09-17",
    }
    model = {"HOUSE_TY": "059.9200A", "LTTOT_TOP_AMOUNT": "38207", "MODEL_NO": "01"}
    c = applyhome.normalize_candidate(notice, model)
    assert c["price_krw"] == 382_070_000
    assert c["exclusive_area_m2"] == 59.92
    assert c["region"] == "경기 의정부시 녹양동 일원"
    assert c["unit_type"] == "059.9200A"


def test_normalize_candidate_includes_new_build_and_move_in_date():
    notice = {"HOUSE_NM": "테스트 단지", "HSSPLY_ADRES": "경기도 의정부시", "TOT_SUPLY_HSHLDCO": 463, "MVN_PREARNGE_YM": "202910"}
    model = {"HOUSE_TY": "059.9200A", "LTTOT_TOP_AMOUNT": "38207", "MODEL_NO": "01"}
    c = applyhome.normalize_candidate(notice, model)
    assert c["new_build"] is True
    assert c["expected_move_in_ym"] == "2029-10"
    assert c["households"] == 463


def test_normalize_candidate_handles_missing_amount():
    notice = {"HOUSE_NM": "x", "HSSPLY_ADRES": "서울특별시 강남구"}
    model = {"HOUSE_TY": "059.0000A", "LTTOT_TOP_AMOUNT": ""}
    c = applyhome.normalize_candidate(notice, model)
    assert c["price_krw"] is None


def test_kst_date_converts_utc_boundary():
    assert kst_date("2026-09-17T23:30:00+00:00") == "2026-09-18"
    assert kst_date("2026-09-18T08:30:00+09:00") == "2026-09-18"


def test_optional_supply_normalizes_suji_fixture():
    fixture_path = Path(__file__).parent / "fixtures" / "applyhome" / "suji_optional.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    notice = applyhome.normalize_notice(fixture["notice"], fixture["supply_type"])
    candidate = applyhome.normalize_candidate(notice, fixture["model"])
    assert candidate["name"] == "수지자이 에디시온"
    assert candidate["supply_type"] == "OPTIONAL"
    assert candidate["region"] == "경기 용인시 수지구 동천동"
    assert candidate["announcement_date"] == "2026-09-16"
    assert candidate["rcept_bgnde"] == "2026-09-18"


def test_fetch_open_notices_paginates_and_stops(monkeypatch):
    calls = []

    def fake_http_get(url, params):
        calls.append(dict(params))
        page = params["page"]
        if page == 1:
            return {"data": [{"PBLANC_NO": str(i)} for i in range(applyhome.PAGE_SIZE)]}
        return {"data": [{"PBLANC_NO": "last"}]}

    monkeypatch.setattr(applyhome, "_http_get", fake_http_get)
    result = applyhome.fetch_open_notices("2026-09-11", ["서울"], "key")
    assert len(result) == applyhome.PAGE_SIZE + 1
    assert calls[0]["page"] == 1 and calls[1]["page"] == 2


def test_fetch_open_notices_without_key_returns_empty():
    assert applyhome.fetch_open_notices("2026-09-11", ["서울"], "") == []


def test_fetch_open_notices_includes_optional_suji_on_receipt_day(monkeypatch):
    fixture = json.loads((Path(__file__).parent / "fixtures" / "applyhome" / "suji_optional.json").read_text(encoding="utf-8"))

    def fake_http_get(url, params):
        if "getOPTLttotPblancDetail" in url:
            return {"data": [fixture["notice"]]}
        return {"data": []}

    monkeypatch.setattr(applyhome, "_http_get", fake_http_get)
    result = applyhome.fetch_open_notices("2026-09-17T23:30:00+00:00", ["경기"], "key")
    assert len(result) == 1
    assert result[0]["HOUSE_NM"] == "수지자이 에디시온"
    assert result[0]["supply_type"] == "OPTIONAL"


def test_fetch_house_models_without_key_returns_empty():
    assert applyhome.fetch_house_models("1", "1", "") == []


def test_search_notices_without_key_or_name_returns_empty():
    assert applyhome.search_notices("", "key") == []
    assert applyhome.search_notices("name", "") == []


def test_search_notices_returns_data(monkeypatch):
    monkeypatch.setattr(applyhome, "_http_get", lambda url, params: {"data": [{"HOUSE_NM": "구리역 하이니티 리버파크"}]})
    result = applyhome.search_notices("하이니티", "key")
    assert result == [{"HOUSE_NM": "구리역 하이니티 리버파크"}]


def test_fetch_house_models_returns_data(monkeypatch):
    monkeypatch.setattr(applyhome, "_http_get", lambda url, params: {"data": [{"MODEL_NO": "01"}]})
    result = applyhome.fetch_house_models("pblanc", "house", "key")
    assert result == [{"MODEL_NO": "01"}]
