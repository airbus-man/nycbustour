# 🚌 NYC Bus Tour 대시보드

NYC 버스 투어 서비스용 운영 대시보드입니다. **Cloudflare Workers + D1(SQLite)** 위에서 동작하고, 별도 서버가 필요 없습니다.

- **KPI**: 매출, 예약 건수, 탑승객, 취소율(직전 기간 대비 증감), 예정된 예약
- **차트**: 일별 매출, 예약 채널(웹/파트너/현장) 비율
- **투어별 실적**: 예약·탑승객·매출·좌석 점유율
- **최근 예약** 목록, 7/30/90일 기간 전환, 60초마다 자동 새로고침, 다크 모드
- **보안**: `DASHBOARD_PASSWORD` 설정 시 Basic Auth, 데이터 입력 API는 `INGEST_TOKEN` Bearer 토큰

## 구조

```
src/index.js                  Worker (API + 인증 + 정적 파일 서빙)
public/index.html             대시보드 UI (외부 의존성 없음)
migrations/0001_init.sql      D1 스키마 (tours, bookings)
seed.sql                      샘플 데이터 (3,000건)
.github/workflows/deploy.yml  main 푸시 시 자동 배포
```

## 1. 로컬에서 실행

```bash
npm install
cp .dev.vars.example .dev.vars      # 필요하면 비밀번호 수정 (DASHBOARD_PASSWORD를 지우면 인증 없이 열림)
npm run db:migrate:local
npm run db:seed:local               # 샘플 데이터
npm run dev                         # http://localhost:8787
```

## 2. Cloudflare에 배포

```bash
npx wrangler login                          # 브라우저로 Cloudflare 로그인
npx wrangler d1 create nycbustour-db        # 출력된 database_id를 wrangler.jsonc에 붙여넣기
npm run db:migrate:remote
npm run db:seed:remote                      # (선택) 샘플 데이터 — 실제 운영 데이터가 있으면 생략

npx wrangler secret put DASHBOARD_PASSWORD  # 대시보드 접속 비밀번호
npx wrangler secret put INGEST_TOKEN        # 예약 입력 API 토큰

npm run deploy                              # → https://nycbustour-dashboard.<계정>.workers.dev
```

> ⚠️ `seed.sql`은 실행할 때마다 `bookings`/`tours` 테이블을 **비우고** 다시 채웁니다. 실제 데이터가 들어간 뒤에는 실행하지 마세요.

- **커스텀 도메인**: Cloudflare 대시보드 → Workers & Pages → `nycbustour-dashboard` → Settings → Domains & Routes 에서 `dashboard.내도메인.com` 등을 연결할 수 있습니다.
- **더 강한 보안이 필요하면** Basic Auth 대신 Cloudflare Zero Trust **Access**를 붙여 이메일/Google 로그인으로 제한하는 것을 권장합니다.

### GitHub Actions 자동 배포

저장소 Settings → Secrets and variables → Actions 에 다음을 추가하면 `main` 푸시 때마다 마이그레이션 + 배포가 실행됩니다. (첫 배포 전에 `wrangler.jsonc`의 `database_id`를 실제 값으로 바꿔야 합니다.)

| Secret | 값 |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | Cloudflare → My Profile → API Tokens → "Edit Cloudflare Workers" 템플릿 + D1 Edit 권한 |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 대시보드 우측 사이드바의 Account ID |

## 3. 서비스에서 예약 데이터 보내기

```bash
curl -X POST https://<배포 URL>/api/bookings \
  -H "Authorization: Bearer $INGEST_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tour_id":1,"customer_name":"Kim","party_size":2,"tour_date":"2026-11-05","channel":"web"}'
```

| 필드 | 필수 | 설명 |
| --- | --- | --- |
| `tour_id` | ✅ | `tours.id` |
| `customer_name` | ✅ | 고객명 |
| `party_size` | ✅ | 인원 (1 이상) |
| `tour_date` | ✅ | `YYYY-MM-DD` |
| `channel` | | `web` \| `partner` \| `walk-in` (기본 `web`) |
| `status` | | `confirmed` \| `completed` \| `cancelled` (기본 `confirmed`) |
| `amount_cents` | | 생략 시 `투어 가격 × 인원` |

투어 추가/수정은 D1 콘솔 또는 `npx wrangler d1 execute nycbustour-db --remote --command "INSERT INTO tours ..."` 로 합니다.

## 조회 API (대시보드가 사용)

`GET /api/summary | daily | tours | channels | recent | health` — 모두 `?days=N`(1–365, 기본 30) 지원. 기간은 **투어 날짜 기준**입니다.
