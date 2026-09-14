import importlib.util
import sys
import tempfile
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

    def test_player_client_parsing_preserves_valid_order(self):
        self.assertEqual(
            helpers.parse_player_clients(" mweb, web_safari, tv, web "),
            ("mweb", "web_safari", "tv", "web"),
        )

    def test_player_client_parsing_ignores_duplicates_and_invalid_values(self):
        self.assertEqual(
            helpers.parse_player_clients("mweb, mweb,invalid,tv, tv"),
            ("mweb", "tv"),
        )

    def test_player_client_parsing_falls_back_to_mweb(self):
        for value in ("", "invalid, nope", None, 123):
            with self.subTest(value=value):
                self.assertEqual(helpers.parse_player_clients(value), ("mweb",))

    def test_public_fallbacks_run_before_cookies(self):
        attempts = helpers.build_attempts(
            pot_enabled=True,
            has_cookies=True,
            player_clients="mweb,web_safari,tv,web",
        )
        self.assertEqual(
            [(attempt.strategy.value, attempt.player_client) for attempt in attempts],
            [
                ("po_token", "mweb"),
                ("anonymous", None),
                ("anonymous", "web_safari"),
                ("anonymous", "tv"),
                ("anonymous", "web"),
                ("cookies", None),
            ],
        )
        self.assertFalse(any(attempt.use_cookies for attempt in attempts[:-1]))
        self.assertTrue(attempts[-1].use_cookies)

    def test_po_token_is_limited_to_mweb(self):
        attempts = helpers.build_attempts(
            pot_enabled=True,
            has_cookies=False,
            player_clients="mweb,web_safari,web",
        )
        self.assertEqual(
            [(attempt.strategy.value, attempt.player_client) for attempt in attempts],
            [
                ("po_token", "mweb"),
                ("anonymous", "web_safari"),
                ("anonymous", "web"),
            ],
        )

    def test_without_po_token_all_clients_are_anonymous(self):
        attempts = helpers.build_attempts(
            pot_enabled=False,
            has_cookies=False,
            player_clients="mweb,web_safari,tv,web",
        )
        self.assertEqual(
            [(attempt.strategy.value, attempt.player_client) for attempt in attempts],
            [
                ("anonymous", None),
                ("anonymous", "mweb"),
                ("anonymous", "web_safari"),
                ("anonymous", "tv"),
                ("anonymous", "web"),
            ],
        )

    def test_cookie_attempt_depends_on_cookie_file_existence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.txt"
            attempts = helpers.build_attempts(
                pot_enabled=False,
                has_cookies=helpers.cookie_file_available(path),
                player_clients="web_safari",
            )
            self.assertEqual(
                [attempt.strategy.value for attempt in attempts],
                ["anonymous", "anonymous"],
            )

            path.write_text(
                "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t0\tSID\tvalue\n",
                encoding="utf-8",
            )
            attempts = helpers.build_attempts(
                pot_enabled=False,
                has_cookies=helpers.cookie_file_available(path),
                player_clients="web_safari",
            )
            self.assertEqual(
                [attempt.strategy.value for attempt in attempts],
                ["anonymous", "anonymous", "cookies"],
            )

    def test_cookies_are_always_last_when_available(self):
        combinations = (
            (True, True),
            (False, True),
        )
        for pot_enabled, has_cookies in combinations:
            with self.subTest(pot_enabled=pot_enabled, has_cookies=has_cookies):
                attempts = helpers.build_attempts(
                    pot_enabled=pot_enabled,
                    has_cookies=has_cookies,
                    player_clients="mweb,web_safari,tv,web",
                )
                self.assertEqual(attempts[-1].strategy.value, "cookies")

    def test_stream_unavailable_has_safe_user_message(self):
        message = helpers.friendly_youtube_error(
            "No audio source found on a resolved YouTube URL"
        )
        self.assertIn("تعذر فتح رابط الوسائط", message)
        self.assertNotIn("No audio source found", message)

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
            "No audio source found on direct URL": "stream_unavailable",
            "No video source found on direct URL": "stream_unavailable",
            "HTTP Error 403: Forbidden": "http_403",
            "HTTP Error 429: Too Many Requests": "rate_limited",
            "PO Token provider unavailable": "po_token_failed",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(helpers.classify_youtube_error(message), expected)

    def test_cookie_rejection_user_message_is_safe_and_practical(self):
        message = helpers.friendly_youtube_error(
            "Sign in to confirm you're not a bot: very long yt-dlp details"
        )
        self.assertIn("المسارات العامة", message)
        self.assertNotIn("yt-dlp details", message)


if __name__ == "__main__":
    unittest.main()
