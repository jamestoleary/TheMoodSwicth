"""Periodic, single-writer SQLite outbox sync to a dedicated Google Sheets tab."""
import argparse
import fcntl
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
HEADERS = ["Event ID", "Recorded at (UTC)", "Button", "Phrase", "Emotion", "Local date", "Local time", "Timezone"]
LOG = logging.getLogger("moodswitch.sync")


class SheetsDestination:
    def __init__(self, config):
        from google.oauth2.service_account import Credentials
        from google.auth.transport.requests import AuthorizedSession
        credentials = Credentials.from_service_account_file(
            str(Path(config["credentials_file"]).expanduser()),
            scopes=["https://www.googleapis.com/auth/spreadsheets"])
        self.session = AuthorizedSession(credentials)
        self.base = "https://sheets.googleapis.com/v4/spreadsheets/" + quote(config["spreadsheet_id"], safe="") + "/values/"
        self.tab = "'" + config.get("tab", "Events").replace("'", "''") + "'"

    def request(self, method, range_name, suffix="", **kwargs):
        response = self.session.request(method, self.base + quote(self.tab + "!" + range_name, safe="") + suffix, timeout=30, **kwargs)
        if not response.ok:
            # Don't log access tokens, credential files, or raw response payloads.
            raise RuntimeError(f"Google Sheets returned HTTP {response.status_code}")
        return response.json()

    def existing_ids(self):
        header = self.request("GET", "A1:H1").get("values", [])
        if not header:
            self.request("PUT", "A1:H1", params={"valueInputOption": "RAW"}, json={"values": [HEADERS]})
        elif header != [HEADERS]:
            raise ValueError("Destination headers differ; use a dedicated Events tab with the documented headers")
        rows = self.request("GET", "A2:A").get("values", [])
        return {row[0] for row in rows if row}

    def append(self, rows):
        result = self.request("POST", "A:H", ":append",
                              params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                              json={"values": rows})
        if result.get("updates", {}).get("updatedRows") != len(rows):
            raise RuntimeError("Google Sheets did not confirm the expected number of rows")


def sync_once(database, destination, labels, timezone_name="Europe/London", limit=100, emotions=None):
    # A fresh remote ID read before every batch reconciles an upload that
    # succeeded remotely but whose acknowledgement was lost during a timeout.
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        pending = [dict(row) for row in db.execute(
            "SELECT id,response,recorded_at FROM events WHERE synced=0 ORDER BY rowid LIMIT ?", (limit,))]
    if not pending:
        return 0
    existing = destination.existing_ids()
    missing = [event for event in pending if event["id"] not in existing]
    rows = []
    for event in missing:
        local = datetime.fromisoformat(event["recorded_at"]).astimezone(ZoneInfo(timezone_name))
        rows.append([event["id"], event["recorded_at"], event["response"],
                     labels.get(event["response"], event["response"]),
                     (emotions or {}).get(event["response"], ""),
                     local.date().isoformat(), local.time().isoformat(), timezone_name])
    if rows:
        destination.append(rows)
    # Only acknowledged uploads and IDs verified as already present are marked.
    with sqlite3.connect(database) as db:
        db.executemany("UPDATE events SET synced=1 WHERE id=?", [(event["id"],) for event in pending])
    return len(pending)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-config", type=Path, default=Path.home() / ".config/moodswitch/sync.json")
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--database", type=Path, default=ROOT / "data/events.db")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if not args.sync_config.is_file():
        parser.error("Google Sheets sync is not configured yet")
    if not args.database.is_file():
        parser.error("Event database does not exist yet; start the recorder first")
    with args.database.with_suffix(".sync.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            LOG.info("Another sync is already running")
            return
        config = json.loads(args.config.read_text())
        destination = SheetsDestination(json.loads(args.sync_config.read_text()))
        try:
            total = 0
            # Limit each run to 1,000 events to avoid monopolising the device.
            for _ in range(10):
                count = sync_once(args.database, destination,
                                  {b["id"]: b["label"] for b in config["buttons"]}, config["timezone"],
                                  emotions={b["id"]: b.get("emotion", "") for b in config["buttons"]})
                total += count
                if count < 100:
                    break
            LOG.info("Synced %s events", total)
        except Exception as error:
            LOG.error("Sync failed (%s); unsynced events remain local for the next run", type(error).__name__)
            raise SystemExit(1)


if __name__ == "__main__":
    main()
