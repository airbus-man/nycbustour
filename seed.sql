-- 샘플 데이터 (실제 데이터가 들어오기 전 대시보드 확인용). 다시 실행하면 초기화됩니다.
DELETE FROM bookings;
DELETE FROM tours;
DELETE FROM sqlite_sequence WHERE name IN ('tours','bookings');

INSERT INTO tours (name, route, duration_min, price_cents, capacity) VALUES
  ('Downtown Loop',        'Times Square → Wall St → Brooklyn Bridge', 120, 5900, 50),
  ('Uptown & Harlem',      'Central Park → Museum Mile → Harlem',      150, 6400, 50),
  ('Night Lights',         'Midtown → Brooklyn Waterfront → Midtown',   90, 7900, 40),
  ('Brooklyn Explorer',    'DUMBO → Williamsburg → Prospect Park',     180, 6900, 30),
  ('Statue Express',       'Midtown → Battery Park (ferry combo)',     210, 9900, 35);

WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 3000),
raw AS MATERIALIZED (
  SELECT
    i,
    1 + abs(random()) % 5                       AS tour_id,
    1 + abs(random()) % 6                       AS party_size,
    abs(random()) % 135 - 120                   AS day_offset,   -- 120일 전 ~ 14일 후
    abs(random()) % 100                         AS r_status,
    abs(random()) % 100                         AS r_channel
  FROM n
)
INSERT INTO bookings (tour_id, customer_name, party_size, amount_cents, channel, status, tour_date, created_at)
SELECT
  raw.tour_id,
  'Guest #' || raw.i,
  raw.party_size,
  raw.party_size * t.price_cents,
  CASE WHEN raw.r_channel < 60 THEN 'web' WHEN raw.r_channel < 88 THEN 'partner' ELSE 'walk-in' END,
  CASE
    WHEN raw.r_status < 9 THEN 'cancelled'
    WHEN raw.day_offset < 0 THEN 'completed'
    ELSE 'confirmed'
  END,
  date('now', raw.day_offset || ' days'),
  min(datetime('now'), datetime('now', (raw.day_offset - 1 - abs(random()) % 20) || ' days', (abs(random()) % 86400) || ' seconds'))
FROM raw JOIN tours t ON t.id = raw.tour_id;
