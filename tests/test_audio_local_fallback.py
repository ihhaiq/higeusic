import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_SOURCE = (ROOT / "AlexaMusic/platforms/Youtube.py").read_text(
    encoding="utf-8"
)
CALL_SOURCE = (ROOT / "AlexaMusic/core/call.py").read_text(encoding="utf-8")


def async_function_source(source: str, name: str) -> str:
    tree = ast.parse(source)
    function = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )
    return ast.get_source_segment(source, function) or ""


class AudioLocalFallbackTest(unittest.TestCase):
    def test_youtube_api_has_unique_audio_download_fallback(self):
        method = async_function_source(YOUTUBE_SOURCE, "download_stream_audio")

        self.assertIn("bestaudio[ext=m4a]/bestaudio/best", method)
        self.assertIn(
            'downloads/stream_{chat_id}_{unique}_%(id)s.%(ext)s',
            method,
        )

    def test_direct_stream_failure_can_download_audio_or_video(self):
        function = async_function_source(CALL_SOURCE, "_play_media_with_fallback")

        self.assertIn("if youtube and allow_local_fallback:", function)
        self.assertIn("YouTube.download_stream_audio", function)
        self.assertIn("YouTube.download_stream_video", function)
        self.assertNotIn(
            "if youtube and video and allow_local_fallback:",
            function,
        )

    def test_finite_tracks_enable_local_fallback(self):
        function = async_function_source(CALL_SOURCE, "join_call")

        self.assertIn(
            "allow_local_fallback=duration_to_seconds(duration) > 0",
            function,
        )

    def test_queued_youtube_tracks_enable_local_fallback(self):
        function = async_function_source(CALL_SOURCE, "change_stream")

        self.assertIn("allow_local_fallback=True", function)


if __name__ == "__main__":
    unittest.main()
