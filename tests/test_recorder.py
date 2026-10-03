import sqlite3
import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from moodswitch.recorder import Recorder


class RecorderTests(unittest.TestCase):
    def test_shared_cooldown_and_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.db"
            now = [0]
            recorder = Recorder(path, clock=lambda: now[0])
            self.assertIsNotNone(recorder.press("button_1"))
            now[0] = 4.99
            self.assertIsNone(recorder.press("button_2"))
            now[0] = 5
            self.assertIsNotNone(recorder.press("button_2"))
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT response, synced FROM events ORDER BY rowid").fetchall(), [("button_1", 0), ("button_2", 0)])

    def test_simultaneous_buttons_record_only_one_event(self):
        with tempfile.TemporaryDirectory() as folder:
            recorder = Recorder(Path(folder) / "events.db", clock=lambda: 0)
            with ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(recorder.press, ["button_1", "button_2", "button_3", "button_4", "button_5"]))
            self.assertEqual(sum(result is not None for result in results), 1)
