import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from moodswitch.app import App
from moodswitch.recorder import Recorder

CONFIG = {"cooldown_seconds": 5, "timezone": "Europe/London", "buttons": [
    {"id": "button_1", "label": "Button 1", "gpio": 17},
    {"id": "button_2", "label": "Button 2", "gpio": 27}]}


class AppTests(unittest.TestCase):
    def test_live_press_visible_even_when_not_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            app = App(CONFIG, Path(folder) / "events.db")
            app.transition("button_1", True)
            app.transition("button_1", False)
            app.transition("button_2", True)
            snapshot = app.snapshot()
            self.assertTrue(snapshot["pressed"]["button_2"])
            self.assertFalse(snapshot["last_press"]["accepted"])
            self.assertEqual(snapshot["totals"]["all"], {"button_1": 1})
            app.transition("button_2", False)
            self.assertFalse(app.snapshot()["pressed"]["button_2"])

    def test_london_calendar_boundaries_and_restart_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.db"
            recorder = Recorder(path)
            # Monday in BST starts at 23:00 UTC on Sunday.
            with sqlite3.connect(path) as db:
                db.executemany("INSERT INTO events (id,response,recorded_at) VALUES (?,?,?)", [
                    ("before", "button_1", "2026-10-04T22:59:59+00:00"),
                    ("at", "button_1", "2026-10-04T23:00:00+00:00"),
                    ("during", "button_2", "2026-10-05T12:00:00+00:00"),
                    ("tomorrow", "button_2", "2026-10-05T23:00:00+00:00")])
            summary = Recorder(path).summary(now=datetime(2026, 10, 5, 14, tzinfo=timezone.utc))
            self.assertEqual(summary["totals"]["today"], {"button_1": 1, "button_2": 1})
            self.assertEqual(summary["totals"]["week"], {"button_1": 1, "button_2": 2})
            self.assertEqual(summary["totals"]["all"], {"button_1": 2, "button_2": 2})
