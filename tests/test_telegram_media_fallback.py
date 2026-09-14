import importlib.util
import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "AlexaMusic/core/telegram_media_fallback.py"
)
SPEC = importlib.util.spec_from_file_location("telegram_media_fallback", MODULE_PATH)
telegram_fallback = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(telegram_fallback)

build_downloader_command = telegram_fallback.build_downloader_command
fetch_media_from_telegram_bot = telegram_fallback.fetch_media_from_telegram_bot
route_telegram_media_fallback_reply = (
    telegram_fallback.route_telegram_media_fallback_reply
)


class FakeMessage:
    def __init__(
        self,
        message_id,
        *,
        username=None,
        reply_to_message_id=None,
        document=None,
        video=None,
        audio=None,
        text=None,
        chat_id=-1001234567890,
    ):
        self.id = message_id
        self.from_user = (
            SimpleNamespace(username=username) if username is not None else None
        )
        self.reply_to_message_id = reply_to_message_id
        self.reply_to_message = None
        self.document = document
        self.video = video
        self.audio = audio
        self.text = text
        self.caption = None
        self.chat = SimpleNamespace(id=chat_id)
        self.deleted = False

    async def delete(self):
        self.deleted = True


class FakeClient:
    def __init__(self, replies):
        self.replies = replies
        self.request = FakeMessage(100, username="MusicBot")
        self.sent = None
        self.downloaded_message = None

    async def send_message(self, chat_id, text, **kwargs):
        self.sent = (chat_id, text, kwargs)
        async def deliver_replies():
            await asyncio.sleep(0)
            for message in self.replies:
                route_telegram_media_fallback_reply(message)

        asyncio.create_task(deliver_replies())
        return self.request

    async def get_chat_history(self, chat_id, limit):
        raise AssertionError("Bot fallback must not read chat history")
        yield

    async def download_media(self, message, file_name):
        self.downloaded_message = (message, file_name)
        return "downloads/external-result.mp4"


class TelegramMediaFallbackTest(unittest.IsolatedAsyncioTestCase):
    def test_command_targets_the_external_bot(self):
        self.assertEqual(
            build_downloader_command(
                "/d",
                "@DownloaderBot",
                "https://youtu.be/example",
            ),
            "/d@downloaderbot https://youtu.be/example",
        )

    async def test_only_correlated_bot_reply_is_downloaded(self):
        unrelated = FakeMessage(
            103,
            username="DownloaderBot",
            reply_to_message_id=99,
            document=object(),
        )
        result = FakeMessage(
            102,
            username="DownloaderBot",
            reply_to_message_id=100,
            video=object(),
        )
        older = FakeMessage(100, username="MusicBot")
        client = FakeClient([unrelated, result, older])

        path = await fetch_media_from_telegram_bot(
            client,
            source_chat_id=-1001234567890,
            bot_username="DownloaderBot",
            command="/v",
            link="https://youtu.be/example",
            request_chat_id=-10099887766,
            cleanup=True,
        )

        self.assertEqual(path, "downloads/external-result.mp4")
        self.assertEqual(
            client.sent[1],
            "/v@downloaderbot https://youtu.be/example",
        )
        self.assertIs(client.downloaded_message[0], result)
        self.assertTrue(client.request.deleted)
        self.assertTrue(result.deleted)

    async def test_timeout_unregisters_the_waiting_request(self):
        client = FakeClient([])

        with self.assertRaises(telegram_fallback.TelegramMediaFallbackError):
            await fetch_media_from_telegram_bot(
                client,
                source_chat_id=-1001234567890,
                bot_username="DownloaderBot",
                command="/v",
                link="https://youtu.be/example",
                request_chat_id=-10099887766,
                response_timeout=0.01,
                cleanup=True,
            )

        late_reply = FakeMessage(
            102,
            username="DownloaderBot",
            reply_to_message_id=100,
            video=object(),
        )
        self.assertFalse(route_telegram_media_fallback_reply(late_reply))
        self.assertTrue(client.request.deleted)


if __name__ == "__main__":
    unittest.main()
