from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "AlexaMusic" / "utils" / "play_request.py"
)
SPEC = importlib.util.spec_from_file_location("play_request_under_test", MODULE_PATH)
play_request = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = play_request
SPEC.loader.exec_module(play_request)


class PlayRequestTests(unittest.TestCase):
    def message(self, text: str, command=None):
        return SimpleNamespace(text=text, caption=None, command=command)

    def test_bare_arabic_video_command(self):
        message = self.message("فيديو اسم الفيديو", ["فيديو", "اسم", "الفيديو"])
        self.assertEqual(play_request.play_command_name(message), "فيديو")
        self.assertTrue(play_request.is_video_request(message))

    def test_prefixed_arabic_video_command(self):
        message = self.message("/فيديو اسم الفيديو", ["فيديو", "اسم", "الفيديو"])
        self.assertTrue(play_request.is_video_request(message))

    def test_vplay_with_bot_suffix(self):
        message = self.message(
            "/vplay@MusicBot example",
            ["vplay@MusicBot", "example"],
        )
        self.assertTrue(play_request.is_video_request(message))

    def test_audio_play_is_not_video(self):
        self.assertFalse(
            play_request.is_video_request(
                self.message("/play example", ["play", "example"])
            )
        )

    def test_standalone_video_option(self):
        self.assertTrue(
            play_request.is_video_request(
                self.message("/play -v example", ["play", "-v", "example"])
            )
        )

    def test_similar_text_is_not_video_option(self):
        self.assertFalse(
            play_request.is_video_request(
                self.message("/play abc-v example", ["play", "abc-v", "example"])
            )
        )


if __name__ == "__main__":
    unittest.main()
