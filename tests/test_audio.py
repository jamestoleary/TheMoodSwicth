import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from moodswitch.audio import find_audio
from moodswitch.app import App


class AudioTests(unittest.TestCase):
    def test_number_matching_and_later_additions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertIsNone(find_audio(root, 1))
            (root / "10-other.wav").touch()
            (root / "1-label.WAV").touch()
            (root / "2-word.wav").touch()
            self.assertEqual(find_audio(root, 1).name, "1-label.WAV")
            (root / "1-duplicate.wav").touch()
            with self.assertRaises(ValueError):
                find_audio(root, 1)

    def test_sound_only_after_saved_response(self):
        with tempfile.TemporaryDirectory() as folder:
            audio = Mock()
            config = {"cooldown_seconds": 5, "timezone": "Europe/London", "buttons": [
                {"id": "button_1", "label": "Button 1", "gpio": 17},
                {"id": "button_2", "label": "Button 2", "gpio": 27}]}
            app = App(config, Path(folder) / "events.db", audio)
            app.transition("button_1", True)
            app.transition("button_1", False)
            app.transition("button_2", True)
            audio.play.assert_called_once_with(1)
