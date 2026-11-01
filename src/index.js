// NYC Bus Tour 대시보드 — Cloudflare Worker
// - GET  /api/*         : 대시보드용 집계 API (D1)
// - POST /api/bookings  : 서비스에서 예약 데이터를 넣는 엔드포인트 (Bearer INGEST_TOKEN)
// - 그 외               : public/ 정적 파일 (대시보드 UI)

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

function clampDays(url) {
  const d = parseInt(url.searchParams.get("days") || "30", 10);
  return Number.isFinite(d) ? Math.min(Math.max(d, 1), 365) : 30;
}

// 타이밍 공격을 피하기 위한 상수 시간 비교
function safeEqual(a, b) {
  const enc = new TextEncoder();
  const x = enc.encode(a), y = enc.encode(b);
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] ?? 0) ^ (y[i] ?? 0);
  return diff === 0;
}

function checkBasicAuth(request, env) {
  if (!env.DASHBOARD_PASSWORD) return true; // 비밀번호 미설정 시 공개
  const h = request.headers.get("authorization") || "";
  if (!h.startsWith("Basic ")) return false;
  try {
    const [, pass = ""] = atob(h.slice(6)).split(/:(.*)/s);
    return safeEqual(pass, env.DASHBOARD_PASSWORD);
  } catch {
    return false;
  }
}

const api = {
  async health(env) {
    const r = await env.DB.prepare("SELECT COUNT(*) AS n FROM bookings").first();
    return { ok: true, bookings: r.n, time: new Date().toISOString() };
  },

  // KPI: 기간 내(투어 날짜 기준, 오늘까지) 매출·예약·탑승객·취소율 + 직전 기간 대비
  async summary(env, days) {
    const sql = `
      SELECT
        COALESCE(SUM(CASE WHEN status != 'cancelled' THEN amount_cents END), 0) AS revenue_cents,
        COUNT(*)                                                                 AS bookings,
        COALESCE(SUM(CASE WHEN status != 'cancelled' THEN party_size END), 0)    AS passengers,
        COALESCE(SUM(status = 'cancelled'), 0)                                   AS cancelled
      FROM bookings
      WHERE tour_date >  date('now', ?1) AND tour_date <= date('now', ?2)`;
    const [cur, prev, upcoming] = await env.DB.batch([
      env.DB.prepare(sql).bind(`-${days} days`, "+0 days"),
      env.DB.prepare(sql).bind(`-${days * 2} days`, `-${days} days`),
      env.DB.prepare(`
        SELECT COUNT(*) AS bookings, COALESCE(SUM(party_size), 0) AS passengers
        FROM bookings WHERE status = 'confirmed' AND tour_date > date('now')`),
    ]);
    return { days, current: cur.results[0], previous: prev.results[0], upcoming: upcoming.results[0] };
  },

  async daily(env, days) {
    const { results } = await env.DB.prepare(`
      SELECT tour_date AS date,
             COALESCE(SUM(CASE WHEN status != 'cancelled' THEN amount_cents END), 0) AS revenue_cents,
             COALESCE(SUM(CASE WHEN status != 'cancelled' THEN party_size END), 0)    AS passengers,
             COUNT(*) AS bookings
      FROM bookings
      WHERE tour_date > date('now', ?1) AND tour_date <= date('now')
      GROUP BY tour_date ORDER BY tour_date`).bind(`-${days} days`).all();
    // 예약이 없는 날도 0으로 채워서 반환
    const byDate = new Map(results.map((r) => [r.date, r]));
    const out = [];
    const today = new Date();
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - i));
      const key = d.toISOString().slice(0, 10);
      out.push(byDate.get(key) || { date: key, revenue_cents: 0, passengers: 0, bookings: 0 });
    }
    return out;
  },

  // 투어별 실적 + 좌석 점유율(운행한 날 기준: 탑승객 / (정원 × 운행일수))
  async tours(env, days) {
    const { results } = await env.DB.prepare(`
      SELECT t.id, t.name, t.route, t.capacity, t.price_cents,
             COUNT(b.id) AS bookings,
             COALESCE(SUM(CASE WHEN b.status != 'cancelled' THEN b.amount_cents END), 0) AS revenue_cents,
             COALESCE(SUM(CASE WHEN b.status != 'cancelled' THEN b.party_size END), 0)    AS passengers,
             COUNT(DISTINCT CASE WHEN b.status != 'cancelled' THEN b.tour_date END)        AS run_days
      FROM tours t
      LEFT JOIN bookings b
        ON b.tour_id = t.id AND b.tour_date > date('now', ?1) AND b.tour_date <= date('now')
      WHERE t.active = 1
      GROUP BY t.id ORDER BY revenue_cents DESC`).bind(`-${days} days`).all();
    return results.map((r) => ({
      ...r,
      occupancy: r.run_days ? r.passengers / (r.capacity * r.run_days) : 0,
    }));
  },

  async channels(env, days) {
    const { results } = await env.DB.prepare(`
      SELECT channel, COUNT(*) AS bookings,
             COALESCE(SUM(CASE WHEN status != 'cancelled' THEN amount_cents END), 0) AS revenue_cents
      FROM bookings
      WHERE tour_date > date('now', ?1) AND tour_date <= date('now')
      GROUP BY channel ORDER BY bookings DESC`).bind(`-${days} days`).all();
    return results;
  },

  async recent(env) {
    const { results } = await env.DB.prepare(`
      SELECT b.id, b.customer_name, b.party_size, b.amount_cents, b.channel, b.status,
             b.tour_date, b.created_at, t.name AS tour_name
      FROM bookings b JOIN tours t ON t.id = b.tour_id
      ORDER BY b.created_at DESC LIMIT 12`).all();
    return results;
  },
};

async function createBooking(request, env) {
  const auth = request.headers.get("authorization") || "";
  if (!env.INGEST_TOKEN || !safeEqual(auth, `Bearer ${env.INGEST_TOKEN}`)) {
    return json({ error: "unauthorized" }, 401);
  }
  let b;
  try {
    b = await request.json();
  } catch {
    return json({ error: "invalid JSON" }, 400);
  }
  const party = parseInt(b.party_size, 10);
  const tourId = parseInt(b.tour_id, 10);
  if (!tourId || !(party > 0) || !/^\d{4}-\d{2}-\d{2}$/.test(b.tour_date || "") || !b.customer_name) {
    return json({ error: "required: tour_id, customer_name, party_size>0, tour_date(YYYY-MM-DD)" }, 400);
  }
  const tour = await env.DB.prepare("SELECT price_cents FROM tours WHERE id = ?").bind(tourId).first();
  if (!tour) return json({ error: "unknown tour_id" }, 400);
  const channel = ["web", "partner", "walk-in"].includes(b.channel) ? b.channel : "web";
  const status = ["confirmed", "completed", "cancelled"].includes(b.status) ? b.status : "confirmed";
  const amount = Number.isInteger(b.amount_cents) ? b.amount_cents : tour.price_cents * party;
  const r = await env.DB.prepare(`
    INSERT INTO bookings (tour_id, customer_name, party_size, amount_cents, channel, status, tour_date)
    VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id`)
    .bind(tourId, String(b.customer_name).slice(0, 200), party, amount, channel, status, b.tour_date)
    .first();
  return json({ ok: true, id: r.id }, 201);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 예약 수집 API는 자체 토큰으로 보호
    if (url.pathname === "/api/bookings" && request.method === "POST") {
      return createBooking(request, env);
    }

    if (!checkBasicAuth(request, env)) {
      return new Response("Authentication required", {
        status: 401,
        headers: { "www-authenticate": 'Basic realm="NYC Bus Tour Dashboard"' },
      });
    }

    if (url.pathname.startsWith("/api/")) {
      if (request.method !== "GET") return json({ error: "method not allowed" }, 405);
      const name = url.pathname.slice(5);
      const handler = Object.hasOwn(api, name) ? api[name] : null;
      if (!handler) return json({ error: "not found" }, 404);
      try {
        return json(await handler(env, clampDays(url)));
      } catch (err) {
        console.error(err);
        return json({ error: "internal error" }, 500);
      }
    }

    return env.ASSETS.fetch(request);
  },
};
