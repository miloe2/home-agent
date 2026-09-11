from pathlib import Path

from home_agent.analyze import analyze_property

CONFIG = str(Path(__file__).parents[1] / "config")

def run(name, **kwargs):
    return analyze_property({"name": name, "unit_type": kwargs.pop("unit_type", "target"), **kwargs}, config_dir=CONFIG, mode="mock")

def test_case_a_small_seoul_is_pass_and_simulation():
    r = run("테스트 서울 소형 A", region="서울", exclusive_area_m2=37.35, price_krw=446000000)
    assert r["verdict"]["status"] == "pass"
    assert r["simulation_only"] is True
    assert r["score"]["components"][0]["value"] == 10
    assert len(r["user_fit"]["questions"]) == 10

def test_case_b_area_and_complex_boundary():
    r = run("테스트 부천 B", region="경기 부천", exclusive_area_m2=52, price_krw=430000000)
    values = {x["id"]: x["value"] for x in r["score"]["components"]}
    assert values["area"] == 80 and values["complex"] == 50

def test_case_c_expensive_small_even_with_large_complex():
    r = run("테스트 구리 C", region="경기 구리", exclusive_area_m2=38, price_krw=670000000)
    values = {x["id"]: x["value"] for x in r["score"]["components"]}
    assert r["verdict"]["status"] == "pass"
    assert values["area"] == 10 and values["budget"] == 50 and values["complex"] == 100

def test_case_d_commute_unknown_is_not_penalized():
    r = run("테스트 외곽 D", region="경기 남양주", exclusive_area_m2=59, price_krw=500000000)
    values = {x["id"]: x["value"] for x in r["score"]["components"]}
    assert values["commute"] is None
    assert "통근" in r["missing_information"]

def test_unknown_property_is_partial_and_has_no_fake_market_data():
    r = run("알 수 없는 단지", region="서울", unit_type="38")
    assert r["identity_status"] == "unresolved"
    assert r["comparable_analysis"]["status"] == "insufficient_information"
    assert r["simulation_only"] is True
