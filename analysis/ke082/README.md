# KE082 (JFK → ICN) 최근 7일 루트·상층풍 분석

Flightradar24 트랙과 Open-Meteo 상층풍(200/250/300 hPa)으로 날짜별로 다음을 계산하고
`dashboard.html`(Leaflet 지도 + Chart.js 차트)로 보여줍니다.

- 루트가 얼마나 북쪽으로 갔는지: 최북단 위도·경도, 경도별 위도 프로파일, 대권항로 대비 우회율
- 상층풍 정풍 성분: 순항 중 시간가중 평균 정풍(kt), 최대 정풍 위치, 50 kt 초과 정풍 시간, 태평양 구간 평균
- 인천 대신 나리타(RJAA)로 간 날짜, 출발 지연, 블록 시간, 기체

## 실행

```bash
cd analysis/ke082
pip install requests
python3 run_all.py                 # 어제까지 7일, FR24 + Open-Meteo 호출
python3 run_all.py --end 2026-11-01 --days 7
python3 run_all.py --offline       # 네트워크 없이 data/ 캐시 + flights_known.json 만으로 재생성
python3 test_pipeline.py           # 합성 데이터로 전체 경로 자체 점검
```

필요한 외부 호스트:

| 용도 | 호스트 |
|---|---|
| 항공편 목록·트랙 | `api.flightradar24.com`, `data-live.flightradar24.com` |
| 상층풍 (GFS 기반, 최근 92일) | `api.open-meteo.com` |
| 대시보드 지도 타일·라이브러리 (브라우저) | `cdnjs.cloudflare.com`, `basemaps.cartocdn.com` |

FR24 비공식 엔드포인트가 막히면 FR24 웹/앱에서 받은 CSV를 `data/tracks/YYYY-MM-DD_*.csv`
(JFK 출발일 기준)로 넣으면 그대로 사용합니다.

## 파일

| 파일 | 역할 |
|---|---|
| `fr24.py` | FR24 항공편 목록·트레일 조회, CSV 내보내기 파서 |
| `winds.py` | 트랙을 15분 간격으로 샘플링해 각 지점·시각의 상층풍 조회 (고도에 가장 가까운 기압면) |
| `geo.py` | 대권거리·방위각, 정풍/측풍 성분 (`headwind = -(u·sinθ + v·cosθ)`, + 정풍) |
| `analyze.py` | 편당 지표 계산, 요약 |
| `build_dashboard.py` | `data/summary.json` → `dashboard.html` |
| `run_all.py` | 전체 실행 |
| `data/flights_known.json` | 수기 입력 사실(출처·검증 여부 포함). FR24 데이터가 있으면 덮어씀 |
| `data/summary.json` | 최종 계산 결과 |

## 데이터 상태 (2026-11-02 생성 시점)

이 세션에서는 flightradar24.com / flightaware.com / skyscanner.com / open-meteo.com 이 네트워크
정책으로 차단되어 트랙과 풍속 데이터를 받지 못했습니다. 공개 검색 스니펫으로 확인된 것은
2026-10-30 출발편(HL7622, A380)이 인천 대신 나리타로 회항했다는 단일 출처 기록뿐이며,
나머지 날짜는 `unknown`으로 남겨 두었습니다. 호스트를 허용한 뒤 `run_all.py`를 다시 실행하면
7일치 지도·차트가 채워집니다.
