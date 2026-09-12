import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "AlexaMusic"
    / "platforms"
    / "youtube_helpers.py"
)
SPEC = importlib.util.spec_from_file_location("youtube_helpers_under_test", MODULE_PATH)
helpers = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = helpers
SPEC.loader.exec_module(helpers)


class YouTubeHelpersTest(unittest.TestCase):
    def test_all_supported_youtube_urls_remain_direct(self):
        urls = (
            "https://www.youtube.com/watch?v=A-n_O-HKyLM&si=tracking",
            "https://youtu.be/A-n_O-HKyLM?si=tracking",
            "https://youtube.com/shorts/A-n_O-HKyLM",
            "https://m.youtube.com/live/A-n_O-HKyLM",
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(helpers.is_youtube_url(url))
                self.assertEqual(helpers.extraction_source(url), url)

    def test_non_youtube_urls_are_not_mistaken_for_youtube(self):
        self.assertFalse(
            helpers.is_youtube_url("https://example.com/youtube.com/video")
        )
        self.assertFalse(helpers.is_youtube_url("https://notyoutube.com/watch?v=123"))

    def test_plain_text_becomes_ytdlp_search(self):
        self.assertEqual(
            helpers.extraction_source("video title", limit=10),
            "ytsearch10:video title",
        )

    def test_auth_attempt_order_with_cookies(self):
        attempts = helpers.build_attempts(pot_enabled=True, has_cookies=True)
        self.assertEqual(
            [attempt.strategy.value for attempt in attempts],
            ["po_token", "cookies", "anonymous"],
        )
        self.assertTrue(attempts[0].use_cookies)
        self.assertFalse(attempts[1].use_plugins)
        self.assertFalse(attempts[2].use_plugins)

    def test_auth_attempt_order_without_cookies(self):
        attempts = helpers.build_attempts(pot_enabled=True, has_cookies=False)
        self.assertEqual(
            [attempt.strategy.value for attempt in attempts],
            ["po_token", "anonymous"],
        )
        self.assertFalse(attempts[0].use_cookies)

    def test_anonymous_is_always_available(self):
        attempts = helpers.build_attempts(pot_enabled=False, has_cookies=False)
        self.assertEqual(
            [attempt.strategy.value for attempt in attempts], ["anonymous"]
        )

    def test_cookies_precede_anonymous_when_pot_is_disabled(self):
        attempts = helpers.build_attempts(pot_enabled=False, has_cookies=True)
        self.assertEqual(
            [attempt.strategy.value for attempt in attempts],
            ["cookies", "anonymous"],
        )

    def test_duration_conversion(self):
        self.assertEqual(helpers.duration_to_seconds("01:02:03"), 3723)
        self.assertEqual(helpers.duration_to_seconds("45:10"), 2710)
        self.assertEqual(helpers.duration_to_seconds(12), 12)
        self.assertEqual(helpers.duration_to_seconds("invalid"), 0)

    def test_error_classification(self):
        cases = {
            "This video is private": "private",
            "Sign in to confirm your age": "age_restricted",
            "Sign in to confirm you're not a bot": "cookies_rejected",
            "No video formats found": "live_unavailable",
            "Video unavailable": "unavailable",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(helpers.classify_youtube_error(message), expected)


if __name__ == "__main__":
    unittest.main()
