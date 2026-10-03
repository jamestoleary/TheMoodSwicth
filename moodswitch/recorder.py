import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone


class Recorder:
    """Persist accepted presses with a shared, thread-safe cooldown."""

    def __init__(self, database, cooldown_seconds=5, clock=time.monotonic):
        if cooldown_seconds < 0:
            raise ValueError("Cooldown must be nonnegative")
        self.database = database
        self.cooldown = cooldown_seconds
        self.clock = clock
        self.lock = threading.Lock()
        self.next_press = float("-inf")
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, response TEXT NOT NULL, recorded_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0)")

    def press(self, response):
        with self.lock:
            now = self.clock()
            if now < self.next_press:
                return None
            event_id = str(uuid.uuid4())
            with sqlite3.connect(self.database) as db:
                db.execute("INSERT INTO events (id, response, recorded_at) VALUES (?, ?, ?)", (event_id, response, datetime.now(timezone.utc).isoformat()))
            self.next_press = now + self.cooldown
            return event_id
