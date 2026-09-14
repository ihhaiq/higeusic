import asyncio
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock


ROOT = Path(__file__).resolve().parents[1]
STREAM_SOURCE = (ROOT / "AlexaMusic/utils/stream/stream.py").read_text(
    encoding="utf-8"
)
spec = importlib.util.spec_from_file_location(
    "playback_progress_under_test",
    ROOT / "AlexaMusic/utils/playback_progress.py",
)
progress = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = progress
spec.loader.exec_module(progress)
format_elapsed = progress.format_elapsed
run_with_progress = progress.run_with_progress


class PlaybackProgressTests(unittest.IsolatedAsyncioTestCase):
    def test_elapsed_time_format(self):
        self.assertEqual(format_elapsed(0), "00:00")
        self.assertEqual(format_elapsed(65), "01:05")
        self.assertEqual(format_elapsed(3661), "01:01:01")

    def test_youtube_stream_reuses_existing_metadata_for_thumbnails(self):
        self.assertIn("gen_thumb(vidid, metadata=result)", STREAM_SOURCE)
        self.assertIn("gen_qthumb(vidid, metadata=result)", STREAM_SOURCE)

    async def test_slow_operation_updates_message_and_returns_result(self):
        message = AsyncMock()

        async def slow_operation():
            await asyncio.sleep(0.035)
            return "ready"

        result = await run_with_progress(
            message,
            slow_operation(),
            video=True,
            initial_delay=0.005,
            interval=0.005,
        )

        self.assertEqual(result, "ready")
        self.assertGreaterEqual(message.edit_text.await_count, 2)
        self.assertIn("الوقت المنقضي", message.edit_text.await_args.args[0])

    async def test_fast_operation_does_not_edit_loading_message(self):
        message = AsyncMock()

        async def fast_operation():
            return "ready"

        result = await run_with_progress(
            message,
            fast_operation(),
            video=False,
            initial_delay=1,
            interval=1,
        )

        self.assertEqual(result, "ready")
        message.edit_text.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
