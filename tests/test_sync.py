import sqlite3
import tempfile
import unittest
from pathlib import Path
from moodswitch.recorder import Recorder
from moodswitch.sync import sync_once


class FakeDestination:
    def __init__(self):
        self.rows = []
        self.fail_after_write = False

    def existing_ids(self):
        return {row[0] for row in self.rows}

    def append(self, rows):
        self.rows.extend(rows)
        if self.fail_after_write:
            self.fail_after_write = False
            raise TimeoutError("Acknowledgement lost")


class SyncTests(unittest.TestCase):
    def test_retry_after_lost_acknowledgement_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.db"
            recorder = Recorder(path, cooldown_seconds=0)
            recorder.press("button_1")
            recorder.press("button_2")
            destination = FakeDestination()
            destination.fail_after_write = True
            with self.assertRaises(TimeoutError):
                sync_once(path, destination, {})
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT SUM(synced) FROM events").fetchone()[0], 0)
            self.assertEqual(sync_once(path, destination, {}), 2)
            self.assertEqual(len(destination.rows), 2)
            self.assertEqual(sync_once(path, destination, {}), 0)

    def test_offline_events_remain_unsynced(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "events.db"
            Recorder(path).press("button_1")
            class Offline:
                def existing_ids(self):
                    raise ConnectionError()
            with self.assertRaises(ConnectionError):
                sync_once(path, Offline(), {})
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE synced=0").fetchone()[0], 1)
