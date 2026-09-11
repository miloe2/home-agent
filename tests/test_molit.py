from pathlib import Path

from home_agent import molit

FIXTURE = Path(__file__).parent / "fixtures" / "molit_sample.xml"
SAMPLE_XML = FIXTURE.read_text(encoding="utf-8")

AUTH_ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OpenAPI_ServiceResponse>
  <cmmMsgHeader>
    <errMsg>SERVICE ERROR</errMsg>
    <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
    <returnReasonCode>30</returnReasonCode>
  </cmmMsgHeader>
</OpenAPI_ServiceResponse>"""

RESULT_ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>03</resultCode><resultMsg>NODATA_ERROR</resultMsg></header>
  <body></body>
</response>"""


def test_resolve_lawd_cd_exact_and_fuzzy():
    table = {"서울 구로구": "11530", "경기 부천": "41190"}
    assert molit.resolve_lawd_cd("서울 구로구", table) == "11530"
    assert molit.resolve_lawd_cd("경기 부천시 원미구", table) == "41190"
    assert molit.resolve_lawd_cd("제주 서귀포", table) is None
    assert molit.resolve_lawd_cd(None, table) is None


def test_resolve_lawd_cd_picks_earliest_mentioned_jurisdiction_in_multi_district_address():
    # Regression: 인천계양 A6 site address lists 인천/경기/서울 jurisdictions together
    # because the project boundary touches all three, but the actual site is the
    # first-named one. A token-count tiebreak alone previously picked 서울 강서구
    # (11500) because it happened to be listed earlier in region_codes.yaml.
    table = {"서울 강서구": "11500", "경기 부천": "41190", "인천 계양구": "28245"}
    region = (
        "인천 계양구 귤현동, 동양동, 박촌동, 병방동, 상야동 및 경기 부천시 대장동, "
        "서울 강서구 오곡동 일원 인천계양 테크노밸리 공공주택지구 내 A6블록"
    )
    assert molit.resolve_lawd_cd(region, table) == "28245"


def test_parse_response_success_includes_raw_cancelled_item():
    parsed = molit._parse_response(SAMPLE_XML)
    assert parsed["status"] == "ok"
    assert parsed["total_count"] == 3
    assert len(parsed["items"]) == 3


def test_parse_response_auth_error():
    parsed = molit._parse_response(AUTH_ERROR_XML)
    assert parsed["status"] == "unavailable"
    assert "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in parsed["reason"]


def test_parse_response_result_code_error():
    parsed = molit._parse_response(RESULT_ERROR_XML)
    assert parsed["status"] == "unavailable"
    assert parsed["reason"] == "NODATA_ERROR"


def test_normalize_item_excludes_cancelled_and_converts_units():
    parsed = molit._parse_response(SAMPLE_XML)
    normalized = [molit._normalize_item(x, "서울 구로구") for x in parsed["items"]]
    normalized = [x for x in normalized if x is not None]
    assert len(normalized) == 2
    assert all("해제" not in x["complex_name"] for x in normalized)
    first = next(x for x in normalized if x["complex_name"] == "테스트합성 아파트A")
    assert first["price_krw"] == 550_000_000
    assert first["area_m2"] == 59.98
    assert first["year"] == 2015


def test_fetch_transactions_live_missing_key_is_unavailable():
    result = molit.fetch_transactions_live("서울 구로구", None, "", {"서울 구로구": "11530"})
    assert result["status"] == "unavailable"
    assert result["transactions"] == []


def test_fetch_transactions_live_unmapped_region_is_unavailable():
    result = molit.fetch_transactions_live("화성 어딘가", None, "fake-key", {"서울 구로구": "11530"})
    assert result["status"] == "unavailable"
    assert result["reason"] == "지역코드 매핑 실패"


def test_fetch_transactions_live_parses_via_monkeypatched_http(monkeypatch):
    monkeypatch.setattr(molit, "_http_get", lambda url, params: SAMPLE_XML)
    result = molit.fetch_transactions_live(
        "서울 구로구", "2025-09-01T00:00:00+00:00", "fake-key", {"서울 구로구": "11530"}, months=1, max_months=1
    )
    assert result["status"] == "ok"
    assert result["months_queried"] == 1
    assert len(result["transactions"]) == 2
    assert all(e["adapter"] == "molit" and e["is_mock"] is False for e in result["evidence"])


def test_fetch_transactions_live_stops_on_http_error(monkeypatch):
    import httpx

    def _boom(url, params):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(molit, "_http_get", _boom)
    result = molit.fetch_transactions_live(
        "서울 구로구", "2025-09-01T00:00:00+00:00", "fake-key", {"서울 구로구": "11530"}, months=12, max_months=24
    )
    assert result["status"] == "unavailable"
    assert result["months_queried"] == 1
    assert result["transactions"] == []
