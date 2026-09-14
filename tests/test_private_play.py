"""Private playback tests with real framework types and no Telegram sessions."""

import asyncio
import importlib.util
import logging
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import FloodWait, UserNotParticipant

ROOT = Path(__file__).resolve().parents[1]


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PrivatePlayTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.chat = NS(id=-1001234567890, username="music_group", title="Music", type=ChatType.SUPERGROUP)
        self.accounts = [NS(
            get_chat=AsyncMock(return_value=self.chat),
            get_chat_member=AsyncMock(return_value=NS(status=ChatMemberStatus.MEMBER)),
        ) for _ in range(2)]
        self.db = NS(
            bind_assistant=AsyncMock(),
            get_assistant=AsyncMock(return_value=self.accounts[0]),
            get_client=AsyncMock(side_effect=lambda number: self.accounts[number - 1]),
            is_active_chat=AsyncMock(return_value=False),
            blacklisted_chats=AsyncMock(return_value=[]),
            get_lang=AsyncMock(return_value="ar"),
            is_served_private_chat=AsyncMock(return_value=True),
        )
        self.config = NS(OWNER_ID=42, BANNED_USERS=filters.user(), PRIVATE_BOT_MODE="False", BOT_TOKEN="unused")
        self.bot = NS(on_message=lambda _filter: lambda function: function)
        self.youtube = NS(url=AsyncMock(return_value=None))
        self.calls = NS(userbot1=NS(get_chat=AsyncMock()), userbot2=NS(get_chat=AsyncMock()))
        self.media = AsyncMock()
        self.modules = {
            "config": self.config,
            "AlexaMusic": NS(app=self.bot, YouTube=self.youtube),
            "AlexaMusic.core.userbot": NS(assistants=[1, 2]),
            "AlexaMusic.core.call": NS(Alexa=self.calls),
            "AlexaMusic.logging": NS(LOGGER=lambda _: logging.getLogger("private-tests")),
            "AlexaMusic.misc": NS(SUDOERS={42, 43}),
            "AlexaMusic.utils.database": self.db,
            "AlexaMusic.plugins.play.play": NS(play_media=self.media),
            "strings": NS(get_string=lambda _: {"general_6": "No active playback"}),
        }
        self.module_patch = patch.dict(sys.modules, self.modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.errors = load_source("AlexaMusic.utils.exceptions", "AlexaMusic/utils/exceptions.py")
        load_source("AlexaMusic.utils.play_request", "AlexaMusic/utils/play_request.py")
        self.resolver = load_source("AlexaMusic.utils.private_play", "AlexaMusic/utils/private_play.py")
        self.handler = load_source("AlexaMusic.plugins.play.private", "AlexaMusic/plugins/play/private.py")

    def message(self, text="فيديو @music_group اسم الفيديو", user_id=42, reply=None):
        return NS(
            text=text, caption=None, from_user=NS(id=user_id),
            chat=NS(id=user_id, type=ChatType.PRIVATE),
            reply_to_message=reply, reply_text=AsyncMock(),
        )

    async def test_resolves_through_assistant_without_bot_membership(self):
        self.assertIs(await self.resolver.resolve_private_chat("@music_group"), self.chat)
        self.accounts[0].get_chat.assert_awaited_once_with("@music_group")

    async def test_rejects_user_destination(self):
        self.chat.type = ChatType.PRIVATE
        with self.assertRaises(self.errors.AssistantErr):
            await self.resolver.resolve_private_chat("@someone")

    async def test_selects_member_assistant_when_default_cannot_join(self):
        self.accounts[0].get_chat_member.side_effect = UserNotParticipant
        self.assertEqual(await self.resolver.prepare_private_assistant(self.chat), 2)
        self.db.bind_assistant.assert_awaited_once_with(self.chat.id, 2)

    async def test_never_reassigns_an_active_destination(self):
        self.db.is_active_chat.return_value = True
        self.accounts[0].get_chat_member.side_effect = UserNotParticipant
        with self.assertRaises(self.errors.AssistantErr):
            await self.resolver.prepare_private_assistant(self.chat)
        self.db.bind_assistant.assert_not_awaited()
        self.accounts[1].get_chat_member.assert_not_awaited()

    async def test_requires_membership_and_does_not_join_automatically(self):
        for account in self.accounts:
            account.get_chat_member.return_value.status = ChatMemberStatus.LEFT
        with self.assertRaises(self.errors.AssistantErr):
            await self.resolver.prepare_private_assistant(self.chat)
        self.db.bind_assistant.assert_not_awaited()

    async def test_floodwait_is_not_hidden_as_missing_membership(self):
        self.accounts[0].get_chat.side_effect = FloodWait(10)
        with self.assertRaises(FloodWait):
            await self.resolver.resolve_private_chat("@music_group")
        self.accounts[1].get_chat.assert_not_awaited()

    async def test_private_command_keeps_dm_for_replies_and_target_for_playback(self):
        message = self.message()
        await self.handler.private_video(None, message)
        args, kwargs = self.media.await_args
        self.assertIs(args[1], message)
        self.assertEqual(args[3], self.chat.id)
        self.assertIs(args[4], True)
        self.assertEqual(kwargs["query"], "اسم الفيديو")
        self.calls.userbot1.get_chat.assert_awaited_once_with("music_group")

    async def test_private_play_command_starts_audio_in_target(self):
        message = self.message("/play @music_group اسم المقطع")
        await self.handler.private_video(None, message)
        args, kwargs = self.media.await_args
        self.assertEqual(args[3], self.chat.id)
        self.assertIs(args[4], False)
        self.assertEqual(kwargs["query"], "اسم المقطع")

    async def test_private_command_accepts_replied_video_without_search(self):
        reply = NS(video=NS(file_id="video"), document=None, audio=None, voice=None)
        message = self.message("فيديو @music_group", reply=reply)
        await self.handler.private_video(None, message)
        self.assertEqual(self.media.await_args.kwargs["query"], "")
        self.assertIs(self.media.await_args.args[1].reply_to_message, reply)

    async def test_unauthorized_user_is_rejected_before_accessing_assistant(self):
        message = self.message(user_id=99)
        await self.handler.private_video(None, message)
        self.accounts[0].get_chat.assert_not_awaited()
        self.media.assert_not_awaited()
        message.reply_text.assert_awaited_once()

    async def test_missing_media_shows_usage_before_target_lookup(self):
        message = self.message("فيديو @music_group")
        await self.handler.private_video(None, message)
        message.reply_text.assert_awaited_once_with(self.handler.USAGE)
        self.accounts[0].get_chat.assert_not_awaited()

    async def test_private_mode_authorizes_target_not_private_chat(self):
        self.config.PRIVATE_BOT_MODE = "True"
        self.db.is_served_private_chat.return_value = False
        await self.handler.private_video(None, self.message())
        self.db.is_served_private_chat.assert_awaited_once_with(self.chat.id)
        self.media.assert_not_awaited()

    async def test_blacklisted_destination_is_rejected(self):
        self.db.blacklisted_chats.return_value = [self.chat.id]
        await self.handler.private_video(None, self.message())
        self.media.assert_not_awaited()

    async def test_different_groups_start_independently_from_same_dm(self):
        second_chat = NS(id=-1009876543210, username="second_group", title="Second", type=ChatType.SUPERGROUP)
        self.handler.resolve_private_chat = AsyncMock(side_effect=[self.chat, second_chat])
        self.handler.prepare_private_assistant = AsyncMock(return_value=1)
        started = set()
        both_started = asyncio.Event()

        async def start(*args, **kwargs):
            started.add(args[3])
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=1)

        self.media.side_effect = start
        await asyncio.gather(
            self.handler.private_video(None, self.message()),
            self.handler.private_video(None, self.message("فيديو @second_group مقطع ثان")),
        )
        self.assertEqual(started, {self.chat.id, second_chat.id})
        self.assertTrue(both_started.is_set())

    async def test_same_group_requests_are_serialized(self):
        running = 0
        maximum = 0

        async def start(*args, **kwargs):
            nonlocal running, maximum
            running += 1
            maximum = max(maximum, running)
            await asyncio.sleep(0)
            running -= 1

        self.media.side_effect = start
        await asyncio.gather(*(
            self.handler.private_video(None, self.message()) for _ in range(2)
        ))
        self.assertEqual(self.media.await_count, 2)
        self.assertEqual(maximum, 1)

    def load_player(self):
        """Load the shared player, mocking only its external service boundaries."""
        self.config.lyrical = {}
        self.config.DURATION_LIMIT = 36000
        self.config.TG_VIDEO_FILESIZE_LIMIT = 1024 * 1024
        self.bot.on_callback_query = lambda _filter: lambda function: function
        self.calls.stream_call = AsyncMock()
        self.youtube.exists = AsyncMock(return_value=True)
        self.youtube.track = AsyncMock(return_value=({
            "vidid": "A-n_O-HKyLM", "title": "Example", "duration_min": "01:00",
            "link": "https://youtu.be/A-n_O-HKyLM", "thumb": "https://example.com/image.jpg",
        }, "A-n_O-HKyLM"))
        self.stream = AsyncMock()
        self.telegram = NS(
            get_filepath=AsyncMock(return_value="/tmp/video.mp4"),
            download=AsyncMock(return_value=True),
            get_link=AsyncMock(return_value=None),
            get_filename=AsyncMock(return_value="video.mp4"),
            get_duration=AsyncMock(return_value="01:00"),
        )
        root = sys.modules["AlexaMusic"]
        for name in ("Apple", "Resso", "SoundCloud", "Spotify"):
            setattr(root, name, NS(valid=AsyncMock(return_value=False)))
        root.Telegram = self.telegram
        self.db.is_video_allowed = AsyncMock(return_value=True)
        sys.modules.update({
            "AlexaMusic.utils": NS(seconds_to_min=lambda _: "01:00", time_to_seconds=lambda _: 60),
            "AlexaMusic.utils.channelplay": NS(get_channeplayCB=AsyncMock()),
            "AlexaMusic.utils.decorators.language": NS(languageCB=lambda fn: fn),
            "AlexaMusic.utils.decorators.play": NS(PlayWrapper=lambda fn: fn),
            "AlexaMusic.utils.formatters": NS(formats=["mp4"]),
            "AlexaMusic.utils.inline.play": NS(**{name: Mock() for name in (
                "livestream_markup", "playlist_markup", "slider_markup", "track_markup",
            )}),
            "AlexaMusic.utils.inline.playlist": NS(botplaylist_markup=Mock()),
            "AlexaMusic.utils.logger": NS(play_logs=AsyncMock()),
            "AlexaMusic.utils.stream.stream": NS(stream=self.stream),
        })
        language = {"play_1": "Loading", "play_2": "Loading {}", "play_11": "{} {}", "str_2": "Streaming"}
        sys.modules["strings"].get_command = lambda _: ["play", "vplay"]
        sys.modules["strings"].get_string = lambda _: language
        self.handler.get_string = lambda _: language
        player = load_source("AlexaMusic.plugins.play.play", "AlexaMusic/plugins/play/play.py")
        self.handler.play_media = player.play_media
        return player

    async def test_private_search_reaches_shared_video_stream_with_correct_target(self):
        self.load_player()
        message = self.message()
        message.from_user.first_name = "Owner"
        message.reply_text.return_value = NS(delete=AsyncMock(), edit_text=AsyncMock())
        await self.handler.private_video(None, message)
        self.youtube.track.assert_awaited_once_with("اسم الفيديو")
        args, kwargs = self.stream.await_args
        self.assertEqual((args[4], args[6]), (self.chat.id, 42))
        self.assertIs(kwargs["video"], True)
        self.assertEqual(kwargs["streamtype"], "youtube")

    async def test_private_livestream_does_not_use_group_confirmation_callback(self):
        self.load_player()
        self.youtube.track.return_value[0]["duration_min"] = None
        message = self.message()
        message.from_user.first_name = "Owner"
        message.reply_text.return_value = NS(delete=AsyncMock(), edit_text=AsyncMock())
        await self.handler.private_video(None, message)
        self.assertEqual(self.stream.await_args.kwargs["streamtype"], "live")
        self.assertEqual(self.stream.await_args.args[4], self.chat.id)

    async def test_private_direct_url_never_plays_in_log_group(self):
        self.load_player()
        self.youtube.exists.return_value = False
        self.youtube.url.return_value = "https://example.com/video.mp4"
        message = self.message("فيديو @music_group https://example.com/video.mp4")
        message.from_user.first_name = "Owner"
        message.reply_text.return_value = NS(delete=AsyncMock(), edit_text=AsyncMock())
        await self.handler.private_video(None, message)
        self.calls.stream_call.assert_not_awaited()
        self.assertEqual(self.stream.await_args.args[4], self.chat.id)
        self.assertEqual(self.stream.await_args.kwargs["streamtype"], "index")

    async def test_private_file_uses_destination_video_policy(self):
        self.load_player()
        reply = NS(video=NS(file_size=100), document=None, audio=None, voice=None)
        message = self.message("فيديو @music_group", reply=reply)
        message.from_user.first_name = "Owner"
        message.reply_text.return_value = NS(delete=AsyncMock(), edit_text=AsyncMock())
        await self.handler.private_video(None, message)
        self.db.is_video_allowed.assert_awaited_once_with(self.chat.id)
        self.assertEqual(self.stream.await_args.kwargs["streamtype"], "telegram")
        self.assertEqual((self.stream.await_args.args[4], self.stream.await_args.args[6]), (self.chat.id, 42))


class RichDestinationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.target = -1001234567890
        self.config = NS(BOT_TOKEN="unused", OWNER_ID=42, BANNED_USERS=set())
        self.active = AsyncMock(return_value=True)
        self.action = AsyncMock()
        dependencies = {
            "config": self.config,
            "AlexaMusic.logging": NS(LOGGER=lambda _: logging.getLogger("rich-tests")),
            "AlexaMusic.misc": NS(SUDOERS={42, 43}),
            "AlexaMusic.utils.database": NS(get_lang=AsyncMock(return_value="ar"), is_active_chat=self.active),
            "AlexaMusic.plugins.admins.callback": NS(
                _can_use_rich_controls=AsyncMock(return_value=True),
                _handle_rich_control_action=self.action,
            ),
            "strings": NS(get_string=lambda _: {"general_6": "No active playback"}),
        }
        self.module_patch = patch.dict(sys.modules, dependencies)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.rich = load_source("AlexaMusic.utils.rich_stream", "AlexaMusic/utils/rich_stream.py")
        self.callbacks = load_source("rich_callbacks_under_test", "AlexaMusic/core/rich_callbacks.py")
        self.bot = NS(send_rich_message=AsyncMock())
        context = Mock()
        context.__aenter__ = AsyncMock(return_value=self.bot)
        context.__aexit__ = AsyncMock(return_value=False)
        self.rich.Bot = Mock(return_value=context)

    def callback(self, data, delivery=42, user=42):
        return NS(
            data=data, id="query", from_user=NS(id=user),
            message=NS(chat=NS(id=delivery)), answer=AsyncMock(),
        )

    async def test_stream_buttons_target_each_group_in_one_dm(self):
        for target in [self.target, -1009876543210]:
            await self.rich.send_stream_rich_message(
                42, playback_chat_id=target, image="https://example.com/image.jpg",
                title="Video", is_video=True, requester_id=42,
            )
            sent = self.bot.send_rich_message.await_args.kwargs
            self.assertEqual(sent["chat_id"], 42)
            data = sent["rich_message"].model_dump_json(exclude_unset=True)
            self.assertIn(f"RICHCTRL {target}|42", data)
            self.assertNotIn("RICHCTRL 42|42", data)

    async def test_private_panel_is_persistent_and_targets_group(self):
        await self.rich.send_control_panel_ephemeral(
            self.target, delivery_chat_id=42, receiver_user_id=42,
            callback_query_id="query", requester_id=42,
        )
        sent = self.bot.send_rich_message.await_args.kwargs
        self.assertEqual(sent["chat_id"], 42)
        self.assertIsNone(sent["ephemeral_message_parameters"])
        data = sent["rich_message"].model_dump_json()
        for command in ("Pause", "Resume", "Stop", "Skip", "Shuffle", "Loop", "1", "2", "3", "4"):
            self.assertIn(f"RCTRL {command}|{self.target}|42", data)

    async def test_existing_group_panel_stays_ephemeral(self):
        await self.rich.send_control_panel_ephemeral(
            self.target, receiver_user_id=42, callback_query_id="query", requester_id=42,
        )
        sent = self.bot.send_rich_message.await_args.kwargs
        self.assertEqual(sent["chat_id"], self.target)
        self.assertEqual(sent["ephemeral_message_parameters"].receiver_user_id, 42)

    async def test_open_callback_uses_message_destination_and_payload_target(self):
        self.callbacks.send_control_panel_ephemeral = AsyncMock()
        callback = self.callback(f"RICHCTRL {self.target}|42")
        await self.callbacks.open_rich_control_panel(callback)
        args, kwargs = self.callbacks.send_control_panel_ephemeral.await_args
        self.assertEqual(args[0], self.target)
        self.assertEqual(kwargs["delivery_chat_id"], 42)
        callback.answer.assert_awaited_once()

    async def test_action_from_dm_controls_only_payload_target(self):
        await self.callbacks.handle_rich_control_action(self.callback(f"RCTRL Pause|{self.target}|42"))
        self.assertEqual(self.action.await_args.args[2:], ("Pause", self.target))
        self.active.assert_awaited_once_with(self.target)

    async def test_private_callback_rejects_spoofed_requester(self):
        callback = self.callback(f"RCTRL Stop|{self.target}|99", delivery=99, user=99)
        await self.callbacks.handle_rich_control_action(callback)
        self.action.assert_not_awaited()
        callback.answer.assert_awaited_once()

    async def test_stale_panel_cannot_control_inactive_chat(self):
        self.active.return_value = False
        await self.callbacks.handle_rich_control_action(self.callback(f"RCTRL Stop|{self.target}|42"))
        self.action.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
