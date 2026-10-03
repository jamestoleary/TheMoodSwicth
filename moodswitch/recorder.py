import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


class Recorder:
    """Persist accepted presses with a shared, thread-safe cooldown."""

    def __init__(self, database, cooldown_seconds=5, clock=time.monotonic,
                 wall_clock=lambda: datetime.now(timezone.utc)):
        if cooldown_seconds < 0:
            raise ValueError("Cooldown must be nonnegative")
        self.database = database
        self.cooldown = cooldown_seconds
        self.clock = clock
        self.wall_clock = wall_clock
        self.lock = threading.Lock()
        self.next_press = float("-inf")
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, response TEXT NOT NULL, recorded_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE INDEX IF NOT EXISTS events_recorded_at ON events(recorded_at)")

    def press(self, response):
        with self.lock:
            now = self.clock()
            if now < self.next_press:
                return None
            event_id = str(uuid.uuid4())
            with sqlite3.connect(self.database) as db:
                db.execute("INSERT INTO events (id, response, recorded_at) VALUES (?, ?, ?)", (event_id, response, self.wall_clock().astimezone(timezone.utc).isoformat()))
            self.next_press = now + self.cooldown
            return event_id

    def cooldown_remaining(self):
        with self.lock:
            return max(0, self.next_press - self.clock())

    def summary(self, timezone_name="Europe/London", now=None):
        local_now = (now or self.wall_clock()).astimezone(ZoneInfo(timezone_name))
        today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        week = today - timedelta(days=today.weekday())
        bounds = {"today": today, "week": week}
        with sqlite3.connect(self.database) as db:
            db.row_factory = sqlite3.Row
            totals = {"all": dict(db.execute("SELECT response, COUNT(*) FROM events GROUP BY response"))}
            for name, start in bounds.items():
                end = today + timedelta(days=1) if name == "today" else week + timedelta(days=7)
                totals[name] = dict(db.execute(
                    "SELECT response, COUNT(*) FROM events WHERE recorded_at >= ? AND recorded_at < ? GROUP BY response",
                    (start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat())))
            recent = [dict(row) for row in db.execute("SELECT id, response, recorded_at FROM events ORDER BY recorded_at DESC, rowid DESC LIMIT 20")]
        return {"totals": totals, "recent": recent, "timezone": timezone_name,
                "day_start": today.isoformat(), "week_start": week.isoformat()}
