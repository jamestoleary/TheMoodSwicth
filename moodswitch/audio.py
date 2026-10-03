"""Discover numbered WAVs and play them away from the GPIO callbacks."""
import logging
import queue
import re
import subprocess
import threading
from pathlib import Path

LOG = logging.getLogger("moodswitch")


def find_audio(folder, number):
    candidates = sorted(path for path in Path(folder).glob("*")
                        if path.is_file() and path.suffix.lower() == ".wav"
                        and re.match(rf"^{number}(?!\d)", path.stem))
    if len(candidates) > 1:
        raise ValueError(f"More than one WAV starts with button number {number}")
    return candidates[0] if candidates else None


class AudioPlayer:
    def __init__(self, folder, device=None):
        self.folder = Path(folder)
        self.device = device
        self.queue = queue.Queue(maxsize=5)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def play(self, number):
        try:
            path = find_audio(self.folder, number)
            if path is None:
                LOG.info("No WAV available yet for button %s", number)
                return
            self.queue.put_nowait(path)
        except (ValueError, queue.Full):
            LOG.exception("Audio could not be queued for button %s", number)

    def _run(self):
        while True:
            path = self.queue.get()
            if path is None:
                self.queue.task_done()
                return
            try:
                command = ["aplay", "-q"]
                if self.device:
                    command += ["-D", self.device]
                subprocess.run(command + [str(path)], check=True, timeout=30,
                               stdin=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                LOG.exception("Audio playback failed for %s; response remains saved", path.name)
            finally:
                self.queue.task_done()

    def close(self):
        # Finish already accepted sounds before stopping the worker.
        self.queue.put(None)
        self.thread.join(timeout=2)
