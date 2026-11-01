CREATE TABLE IF NOT EXISTS tours (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  name         TEXT    NOT NULL,
  route        TEXT    NOT NULL,
  duration_min INTEGER NOT NULL,
  price_cents  INTEGER NOT NULL,
  capacity     INTEGER NOT NULL,
  active       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS bookings (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  tour_id       INTEGER NOT NULL REFERENCES tours(id),
  customer_name TEXT    NOT NULL,
  party_size    INTEGER NOT NULL CHECK (party_size > 0),
  amount_cents  INTEGER NOT NULL,
  channel       TEXT    NOT NULL DEFAULT 'web',       -- web | partner | walk-in
  status        TEXT    NOT NULL DEFAULT 'confirmed', -- confirmed | completed | cancelled
  tour_date     TEXT    NOT NULL,                     -- YYYY-MM-DD
  created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bookings_tour_date ON bookings(tour_date);
CREATE INDEX IF NOT EXISTS idx_bookings_tour_id   ON bookings(tour_id);
CREATE INDEX IF NOT EXISTS idx_bookings_created   ON bookings(created_at);
