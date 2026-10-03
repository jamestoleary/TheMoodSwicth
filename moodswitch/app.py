"""GPIO event recorder and a read-only dashboard served on loopback."""
import argparse
import json
import logging
import signal
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone

from .recorder import Recorder
from .audio import AudioPlayer

ROOT = Path(__file__).resolve().parent.parent
LOG = logging.getLogger("moodswitch")


class App:
    def __init__(self, config, database, audio=None):
        self.config = config
        self.recorder = Recorder(database, config["cooldown_seconds"])
        self.lock = threading.Lock()
        self.pressed = {button["id"]: False for button in config["buttons"]}
        self.transitions = []
        self.sequence = 0
        self.last_press = None
        self.audio = audio
        self.button_numbers = {b["id"]: i for i, b in enumerate(config["buttons"], 1)}

    def transition(self, response, pressed):
        with self.lock:
            self.pressed[response] = pressed
            event_id = None
            error = None
            if pressed:
                try:
                    event_id = self.recorder.press(response)
                except Exception:
                    LOG.exception("Could not save response %s", response)
                    error = "Response could not be saved"
            self.sequence += 1
            event = {"sequence": self.sequence, "response": response,
                     "pressed": pressed, "accepted": bool(event_id),
                     "recorded_at": datetime.now(timezone.utc).isoformat(),
                     "error": error}
            self.transitions.append(event)
            self.transitions = self.transitions[-100:]
            if pressed:
                self.last_press = event
                LOG.info("%s: %s", response, "SAVE FAILED" if error else "saved" if event_id else "ignored during cooldown")
            if event_id and self.audio:
                self.audio.play(self.button_numbers[response])

    def snapshot(self):
        with self.lock:
            data = self.recorder.summary(self.config["timezone"])
            data.update(buttons=self.config["buttons"], pressed=dict(self.pressed),
                        transitions=list(self.transitions), last_press=self.last_press,
                        cooldown_remaining=self.recorder.cooldown_remaining(),
                        cooldown_seconds=self.config["cooldown_seconds"])
            return data


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/status":
                try:
                    payload = json.dumps(app.snapshot()).encode()
                except Exception:
                    LOG.exception("Dashboard status failed")
                    self.send_error(500)
                    return
                content_type = "application/json"
            elif self.path in ("/", "/index.html"):
                payload = (ROOT / "moodswitch" / "dashboard.html").read_bytes()
                content_type = "text/html; charset=utf-8"
            elif self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "events.db")
    parser.add_argument("--host", default="127.0.0.1", help="Dashboard listen address")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-gpio", action="store_true", help="Dashboard preview without physical inputs")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    config = json.loads(args.config.read_text())
    ids = [b["id"] for b in config["buttons"]]
    pins = [b["gpio"] for b in config["buttons"]]
    if not ids or len(set(ids)) != len(ids) or len(set(pins)) != len(pins):
        raise ValueError("Buttons must have unique IDs and GPIO inputs")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    audio = None if args.no_gpio else AudioPlayer(ROOT / "audio", config.get("audio_device"))
    app = App(config, args.database, audio=audio)
    buttons = []
    server = None
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    try:
        if not args.no_gpio:
            from gpiozero import Button
            for entry in config["buttons"]:
                button = Button(entry["gpio"], pull_up=True, bounce_time=config["debounce_seconds"])
                buttons.append(button)
                button.when_pressed = partial(app.transition, entry["id"], True)
                button.when_released = partial(app.transition, entry["id"], False)
                # An already held input is visible but isn't counted as a new press.
                with app.lock:
                    app.pressed[entry["id"]] = button.is_pressed
        server = ThreadingHTTPServer((args.host, args.port), handler_for(app))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        LOG.info("Dashboard listening on %s:%s", args.host, args.port)
        stop.wait()
    finally:
        for button in buttons:
            button.close()
        if server:
            server.shutdown()
            server.server_close()
        if audio:
            audio.close()


if __name__ == "__main__":
    main()
