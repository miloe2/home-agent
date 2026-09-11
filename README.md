# Home Agent

개인용 아파트 구매 의사결정 분석 백엔드입니다. 현재는 외부 API와 DB 없이 합성 mock 자료로 Phase 1~2를 실행합니다. 결과의 `simulation_only`가 `true`이면 실제 단지의 근거로 사용하지 마세요.

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
HOME_AGENT_SOURCE_MODE=mock python -m uvicorn home_agent.main:app --host 127.0.0.1 --port 8000
```

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/analyze -H 'Content-Type: application/json' \
  -d '{"name":"테스트 서울 소형 A","region":"서울 구로구","unit_type":"37A","exclusive_area_m2":37.35,"price_krw":446000000}'
```

`data/reports/`에 JSON 결과가 저장됩니다. `GET /profile`, `POST /profile/validate`, `GET /reports/{property_slug}`도 제공합니다.

## Live 모드 (국토부 실거래가 연결)

`HOME_AGENT_SOURCE_MODE=live` + `HOME_AGENT_MOLIT_API_KEY`(공공데이터포털 발급키, `국토교통부_아파트 매매 실거래가 자료` 활용신청 승인 필요)가 설정되면 `/analyze`가 국토교통부 아파트매매 실거래 API(`getRTMSDataSvcAptTrade`)에서 최근 12개월(부족하면 24개월) 실거래를 조회해 `nearby_comparables`/`comparable_analysis`에 반영합니다. `region`은 `config/region_codes.yaml`에 등록된 시군구 이름과 매칭되어야 법정동코드로 변환됩니다(현재 서울 25개 구 + 경기 주요 시군 등록, 필요시 YAML에 추가).

```bash
HOME_AGENT_SOURCE_MODE=live python -m uvicorn home_agent.main:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/analyze -H 'Content-Type: application/json' \
  -d '{"name":"<실제 아파트명>","region":"서울 구로구","unit_type":"<주택형>","exclusive_area_m2":59.9}'
```

응답의 `evidence[]`에서 `adapter":"molit"`, `"is_mock":false` 항목과 `comparable_analysis.sample_count`를 확인하면 실거래가 실제로 반영되었는지 알 수 있습니다. `sale_history`, `recent_new_supply_comparables`, `alternatives`, `location_analysis`는 LH·지오코딩 adapter가 아직 연결되지 않아 계속 비어있거나 `unavailable`로 표시됩니다(추정치로 채우지 않음).

현재 mock/live 상태: 실거래(국토부)는 live 연결됨. 단지 정보, 분양이력, 입지, 신규분양, 대체재, LH 공고, 금융 규칙은 아직 mock/미구현입니다. LLM은 사용하지 않습니다.
