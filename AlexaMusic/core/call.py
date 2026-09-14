# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio
import contextlib
from typing import Union

from ntgcalls import TelegramServerError
from pyrogram import Client
from pyrogram.errors import ChatAdminRequired, FloodWait
from pytgcalls import PyTgCalls
from pytgcalls import filters as fl
from pytgcalls.exceptions import (
    NoActiveGroupCall,
    NoAudioSourceFound,
    NoVideoSourceFound,
    YtDlpError,
)
from pytgcalls.types import (
    AudioQuality,
    ChatUpdate,
    GroupCallConfig,
    MediaStream,
    StreamEnded,
    VideoQuality,
)

import config
from AlexaMusic import LOGGER, YouTube, app
from AlexaMusic.misc import db
from AlexaMusic.platforms.youtube_helpers import duration_to_seconds
from AlexaMusic.utils.database import (
    add_active_chat,
    add_active_video_chat,
    get_audio_bitrate,
    get_lang,
    get_loop,
    get_video_bitrate,
    group_assistant,
    music_on,
    remove_active_chat,
    remove_active_video_chat,
    set_loop,
)
from AlexaMusic.utils.exceptions import AssistantErr
from AlexaMusic.utils.rich_stream import send_stream_rich_message
from AlexaMusic.utils.stream.autoclear import auto_clean
from AlexaMusic.utils.thumbnails import gen_thumb
from strings import get_string

autoend = {}
counter = {}
AUTO_END_TIME = 1


async def _video_quality_for_duration(chat_id: int, duration=None):
    quality = await get_video_bitrate(chat_id)
    threshold = max(0, int(getattr(config, "LONG_VIDEO_THRESHOLD_MIN", 30))) * 60
    if threshold and duration_to_seconds(duration) >= threshold:
        cap = int(getattr(config, "LONG_VIDEO_MAX_QUALITY", 480))
        LOGGER(__name__).info(
            "Quality reduced to %sp because duration > configured threshold "
            "chat_id=%s duration=%s threshold_minutes=%s",
            cap,
            chat_id,
            duration,
            config.LONG_VIDEO_THRESHOLD_MIN,
        )
        if cap <= 360:
            return VideoQuality.SD_360p
        if cap <= 480:
            return VideoQuality.SD_480p
        if cap <= 720:
            return VideoQuality.HD_720p
        return VideoQuality.FHD_1080p
    return quality


def _media_stream(
    link,
    *,
    audio_link=None,
    audio_quality,
    video_quality=None,
    video=False,
    image=None,
    strict=False,
):
    kwargs = {
        "audio_parameters": audio_quality,
    }
    if video:
        kwargs["video_parameters"] = video_quality
        if strict:
            kwargs["audio_flags"] = MediaStream.Flags.REQUIRED
            kwargs["video_flags"] = MediaStream.Flags.REQUIRED
        # Always give PyTgCalls an explicit audio input for video playback.
        # For progressive YouTube formats this is the same A/V URL; for DASH
        # formats it is the separately resolved audio URL.
        kwargs["audio_path"] = audio_link or link
        return MediaStream(link, **kwargs)
    if image and config.PRIVATE_BOT_MODE == str(True):
        kwargs["video_parameters"] = video_quality
        kwargs["audio_path"] = link
        if strict:
            kwargs["audio_flags"] = MediaStream.Flags.REQUIRED
        return MediaStream(image, **kwargs)
    if strict:
        kwargs["audio_flags"] = MediaStream.Flags.REQUIRED
    kwargs["video_flags"] = MediaStream.Flags.IGNORE
    return MediaStream(link, **kwargs)


def _quality_height(video_quality) -> int:
    if hasattr(video_quality, "height"):
        return int(video_quality.height)
    values = getattr(video_quality, "value", ())
    dimensions = [value for value in values[:2] if isinstance(value, int)]
    return min(dimensions) if dimensions else 720


async def _play_media_with_fallback(
    player,
    chat_id: int,
    link,
    *,
    audio_quality,
    video_quality=None,
    video=False,
    image=None,
    group_config=None,
):
    youtube = isinstance(link, str) and YouTube.is_youtube_url(link)
    LOGGER(__name__).info(
        "Preparing media stream chat_id=%s mode=%s source=%s",
        chat_id,
        "video" if video else "audio",
        "youtube" if youtube else "direct",
    )
    attempts = YouTube.stream_attempts() if youtube else (None,)
    errors = []
    for attempt in attempts:
        stream_link = link
        audio_link = None
        if attempt is not None:
            YouTube.log_attempt(attempt, operation="stream", chat_id=chat_id)
            try:
                stream_link, audio_link = await YouTube.resolve_stream(
                    link,
                    attempt,
                    video=video,
                    max_height=_quality_height(video_quality),
                )
            except Exception as error:
                errors.append(error)
                YouTube.log_failure(
                    attempt,
                    error,
                    operation="stream",
                    chat_id=chat_id,
                )
                continue
        stream = _media_stream(
            stream_link,
            audio_link=audio_link,
            audio_quality=audio_quality,
            video_quality=video_quality,
            video=video,
            image=image,
            strict=youtube,
        )
        try:
            kwargs = {"config": group_config} if group_config is not None else {}
            await player.play(chat_id, stream, **kwargs)
            if youtube:
                LOGGER(__name__).info(
                    "Streaming directly from YouTube chat_id=%s strategy=%s mode=%s",
                    chat_id,
                    attempt.strategy.value,
                    "video" if video else "audio",
                )
            return
        except (YtDlpError, NoAudioSourceFound, NoVideoSourceFound) as error:
            if attempt is None:
                raise
            errors.append(error)
            YouTube.log_failure(
                attempt,
                error,
                operation="stream",
                chat_id=chat_id,
            )
    raise AssistantErr(YouTube.friendly_error(errors[-1]))


async def _clear_(chat_id):
    if popped := db.pop(chat_id, None):
        await auto_clean(popped)
    db[chat_id] = []
    await remove_active_video_chat(chat_id)
    await remove_active_chat(chat_id)
    await set_loop(chat_id, 0)


class Call(PyTgCalls):
    def __init__(self):
        self.userbot1 = Client(
            name="Alexa1",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING1),
        )
        self.one = PyTgCalls(
            self.userbot1,
            cache_duration=2,
        )
        self.userbot2 = Client(
            name="Alexa2",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING2),
        )
        self.two = PyTgCalls(
            self.userbot2,
            cache_duration=2,
        )
        self.userbot3 = Client(
            name="Alexa3",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING3),
        )
        self.three = PyTgCalls(
            self.userbot3,
            cache_duration=2,
        )
        self.userbot4 = Client(
            name="Alexa4",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING4),
        )
        self.four = PyTgCalls(
            self.userbot4,
            cache_duration=2,
        )
        self.userbot5 = Client(
            name="Alexa5",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=str(config.STRING5),
        )
        self.five = PyTgCalls(
            self.userbot5,
            cache_duration=2,
        )

    async def pause_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.resume(chat_id)

    async def mute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.mute(chat_id)

    async def unmute_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        await assistant.unmute(chat_id)

    async def stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        with contextlib.suppress(Exception):
            await _clear_(chat_id)
            await assistant.leave_call(chat_id)

    async def force_stop_stream(self, chat_id: int):
        assistant = await group_assistant(self, chat_id)
        with contextlib.suppress(Exception):
            check = db.get(chat_id)
            check.pop(0)
        await remove_active_video_chat(chat_id)
        await remove_active_chat(chat_id)
        with contextlib.suppress(Exception):
            await assistant.leave_call(chat_id)

    async def skip_stream(
        self,
        chat_id: int,
        link: str,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
    ):
        assistant = await group_assistant(self, chat_id)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        ksk = GroupCallConfig(auto_start=False)
        if video:
            stream = MediaStream(
                link,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
            )
        else:
            if image and config.PRIVATE_BOT_MODE == str(True):
                stream = MediaStream(
                    link,
                    image,
                    audio_parameters=audio_stream_quality,
                    video_parameters=video_stream_quality,
                )
            else:
                stream = MediaStream(
                    link,
                    audio_parameters=audio_stream_quality,
                    video_flags=MediaStream.Flags.IGNORE,
                )
        await assistant.play(
            chat_id,
            stream,
            config=ksk,
        )

    async def seek_stream(self, chat_id, file_path, to_seek, duration, mode):
        assistant = await group_assistant(self, chat_id)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = await get_video_bitrate(chat_id)
        stream = (
            MediaStream(
                file_path,
                audio_parameters=audio_stream_quality,
                video_parameters=video_stream_quality,
                ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
            )
            if mode == "video"
            else MediaStream(
                file_path,
                audio_parameters=audio_stream_quality,
                ffmpeg_parameters=f"-ss {to_seek} -to {duration}",
                video_flags=MediaStream.Flags.IGNORE,
            )
        )
        await assistant.play(chat_id, stream)

    async def stream_call(self, link):
        assistant = await group_assistant(self, config.LOG_GROUP_ID)
        await assistant.play(
            config.LOG_GROUP_ID,
            MediaStream(
                link,
                audio_parameters=AudioQuality.STUDIO,
                video_parameters=VideoQuality.FHD_1080p,
            ),
        )
        await asyncio.sleep(10)
        await assistant.leave_call(config.LOG_GROUP_ID)

    async def join_call(
        self,
        chat_id: int,
        original_chat_id: int,
        link,
        video: Union[bool, str] = None,
        image: Union[bool, str] = None,
        duration=None,
    ):
        assistant = await group_assistant(self, chat_id)
        ksk = GroupCallConfig(auto_start=False)
        audio_stream_quality = await get_audio_bitrate(chat_id)
        video_stream_quality = (
            await _video_quality_for_duration(chat_id, duration)
            if video
            else await get_video_bitrate(chat_id)
        )

        no_active_retried = False
        while True:
            try:
                await _play_media_with_fallback(
                    assistant,
                    chat_id,
                    link,
                    audio_quality=audio_stream_quality,
                    video_quality=video_stream_quality,
                    video=bool(video),
                    image=image,
                    group_config=ksk,
                )
                break
            except ChatAdminRequired:
                raise AssistantErr(
                    "الحساب المساعد لا يملك الصلاحيات اللازمة للانضمام إلى المحادثة الصوتية."
                )
            except TelegramServerError:
                raise AssistantErr(
                    "حدث خطأ من خوادم Telegram أثناء الانضمام للمحادثة الصوتية. حاول مرة أخرى بعد قليل."
                )
            except NoActiveGroupCall:
                if no_active_retried:
                    LOGGER(__name__).warning(
                        "لم يتم العثور على محادثة صوتية فعالة بعد إعادة الفحص: chat_id=%s",
                        chat_id,
                    )
                    raise AssistantErr(
                        "المحادثة الصوتية تبدو مفتوحة، لكن الحساب المساعد لا يستطيع رؤيتها. "
                        "تأكد أن الاتصال مفتوح في المجموعة/القناة المستهدفة "
                        "وأن الحساب المساعد عضو فيها، ثم حاول مرة أخرى."
                    )
                no_active_retried = True
                LOGGER(__name__).warning(
                    "لم يكتشف PyTgCalls المحادثة الصوتية في %s من المحاولة الأولى؛ "
                    "سنعيد الفحص بعد انتهاء الكاش القصير.",
                    chat_id,
                )
                await asyncio.sleep(3)
        await add_active_chat(chat_id)
        await music_on(chat_id)
        if video:
            await add_active_video_chat(chat_id)
        # if await is_autoend():
        #     counter[chat_id] = {}
        #     users = len(await assistant.get_participants(chat_id))
        #     if users == 1:
        #         autoend[chat_id] = datetime.now() + timedelta(minutes=AUTO_END_TIME)

    async def change_stream(self, client, chat_id):
        check = db.get(chat_id)
        popped = None
        loop = await get_loop(chat_id)
        try:
            if loop == 0:
                popped = check.pop(0)
            else:
                loop = loop - 1
                await set_loop(chat_id, loop)
            if popped and config.AUTO_DOWNLOADS_CLEAR == str(True):
                await auto_clean(popped)
            if not check:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
        except Exception:
            try:
                await _clear_(chat_id)
                return await client.leave_call(chat_id)
            except Exception:
                return
        else:
            queued = check[0]["file"]
            language = await get_lang(chat_id)
            _ = get_string(language)
            title = (check[0]["title"]).title()
            original_chat_id = check[0]["chat_id"]
            streamtype = check[0]["streamtype"]
            audio_stream_quality = await get_audio_bitrate(chat_id)
            video_stream_quality = await _video_quality_for_duration(
                chat_id, check[0].get("dur")
            )
            videoid = check[0]["vidid"]
            check[0]["played"] = 0
            video = str(streamtype) == "video"
            if "live_" in queued:
                link = f"https://www.youtube.com/watch?v={videoid}"
                try:
                    image = None
                    if not video:
                        try:
                            image = await YouTube.thumbnail(videoid, True)
                        except Exception:
                            image = None
                    await _play_media_with_fallback(
                        client,
                        chat_id,
                        link,
                        audio_quality=audio_stream_quality,
                        video_quality=video_stream_quality,
                        video=video,
                        image=image,
                    )
                except AssistantErr as error:
                    return await app.send_message(
                        original_chat_id,
                        text=str(error),
                    )
                except Exception:
                    LOGGER(__name__).exception(
                        "فشل تشغيل بث YouTube مباشر من قائمة الانتظار: chat_id=%s video_id=%s",
                        chat_id,
                        videoid,
                    )
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_9"],
                    )
                # theme = await check_theme(chat_id)
                img = await gen_thumb(videoid)
                requester_id = check[0].get("user_id") or config.OWNER_ID
                run = await send_stream_rich_message(
                    original_chat_id,
                    playback_chat_id=chat_id,
                    image=img,
                    title=title,
                    is_video=str(streamtype) == "video",
                    requester_id=requester_id,
                    info_url=f"https://t.me/{app.username}?start=info_{videoid}",
                    duration=check[0]["dur"],
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "rich"
            elif "vid_" in queued:
                mystic = await app.send_message(original_chat_id, _["call_10"])
                file_path = f"https://www.youtube.com/watch?v={videoid}"
                try:
                    image = None
                    if not video:
                        try:
                            image = await YouTube.thumbnail(videoid, True)
                        except Exception:
                            image = None
                    await _play_media_with_fallback(
                        client,
                        chat_id,
                        file_path,
                        audio_quality=audio_stream_quality,
                        video_quality=video_stream_quality,
                        video=video,
                        image=image,
                    )
                except AssistantErr as error:
                    return await mystic.edit_text(
                        str(error),
                        disable_web_page_preview=True,
                    )
                except Exception:
                    LOGGER(__name__).exception(
                        "فشل تشغيل عنصر YouTube من قائمة الانتظار: chat_id=%s video_id=%s",
                        chat_id,
                        videoid,
                    )
                    return await mystic.edit_text(
                        _["call_9"], disable_web_page_preview=True
                    )
                # theme = await check_theme(chat_id)
                img = await gen_thumb(videoid)
                requester_id = check[0].get("user_id") or config.OWNER_ID
                await mystic.delete()
                run = await send_stream_rich_message(
                    original_chat_id,
                    playback_chat_id=chat_id,
                    image=img,
                    title=title,
                    is_video=str(streamtype) == "video",
                    requester_id=requester_id,
                    info_url=f"https://t.me/{app.username}?start=info_{videoid}",
                    duration=check[0]["dur"],
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "rich"
            elif "index_" in queued:
                stream = (
                    MediaStream(
                        videoid,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                    )
                    if str(streamtype) == "video"
                    else MediaStream(
                        videoid,
                        audio_parameters=audio_stream_quality,
                        video_flags=MediaStream.Flags.IGNORE,
                    )
                )
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_9"],
                    )
                requester_id = check[0].get("user_id") or config.OWNER_ID
                run = await send_stream_rich_message(
                    original_chat_id,
                    playback_chat_id=chat_id,
                    image=config.STREAM_IMG_URL,
                    title="بث مباشر من رابط",
                    is_video=str(streamtype) == "video",
                    requester_id=requester_id,
                    duration=check[0]["dur"],
                )
                db[chat_id][0]["mystic"] = run
                db[chat_id][0]["markup"] = "rich"
            else:
                if videoid in ["telegram", "soundcloud"]:
                    image = None
                else:
                    try:
                        image = await YouTube.thumbnail(videoid, True)
                    except Exception:
                        image = None
                if video:
                    stream = MediaStream(
                        queued,
                        audio_parameters=audio_stream_quality,
                        video_parameters=video_stream_quality,
                    )
                else:
                    if image and config.PRIVATE_BOT_MODE == str(True):
                        stream = MediaStream(
                            queued,
                            image,
                            audio_parameters=audio_stream_quality,
                            video_parameters=video_stream_quality,
                        )
                    else:
                        stream = MediaStream(
                            queued,
                            audio_parameters=audio_stream_quality,
                            video_flags=MediaStream.Flags.IGNORE,
                        )
                try:
                    await client.play(chat_id, stream)
                except Exception:
                    return await app.send_message(
                        original_chat_id,
                        text=_["call_9"],
                    )
                if videoid == "telegram":
                    requester_id = check[0].get("user_id") or config.OWNER_ID
                    run = await send_stream_rich_message(
                        original_chat_id,
                        playback_chat_id=chat_id,
                        image=(
                            config.TELEGRAM_AUDIO_URL
                            if str(streamtype) == "audio"
                            else config.TELEGRAM_VIDEO_URL
                        ),
                        title=title,
                        is_video=str(streamtype) == "video",
                        requester_id=requester_id,
                        duration=check[0]["dur"],
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "rich"
                elif videoid == "soundcloud":
                    requester_id = check[0].get("user_id") or config.OWNER_ID
                    run = await send_stream_rich_message(
                        original_chat_id,
                        playback_chat_id=chat_id,
                        image=config.SOUNCLOUD_IMG_URL,
                        title=title,
                        is_video=False,
                        requester_id=requester_id,
                        duration=check[0]["dur"],
                    )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "rich"
                else:
                    # theme = await check_theme(chat_id)
                    img = await gen_thumb(videoid)
                    requester_id = check[0].get("user_id") or config.OWNER_ID
                    try:
                        run = await send_stream_rich_message(
                            original_chat_id,
                            playback_chat_id=chat_id,
                            image=img,
                            title=title,
                            is_video=str(streamtype) == "video",
                            requester_id=requester_id,
                            info_url=f"https://t.me/{app.username}?start=info_{videoid}",
                            duration=check[0]["dur"],
                        )
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        run = await send_stream_rich_message(
                            original_chat_id,
                            playback_chat_id=chat_id,
                            image=img,
                            title=title,
                            is_video=str(streamtype) == "video",
                            requester_id=requester_id,
                            info_url=f"https://t.me/{app.username}?start=info_{videoid}",
                            duration=check[0]["dur"],
                        )
                    db[chat_id][0]["mystic"] = run
                    db[chat_id][0]["markup"] = "rich"

    async def ping(self):
        pings = []
        if config.STRING1:
            pings.append(self.one.ping)
        if config.STRING2:
            pings.append(self.two.ping)
        if config.STRING3:
            pings.append(self.three.ping)
        if config.STRING4:
            pings.append(self.four.ping)
        if config.STRING5:
            pings.append(self.five.ping)
        return str(round(sum(pings) / len(pings), 3))

    async def start(self):
        LOGGER(__name__).info("Starting PyTgCalls Client\n")
        if config.STRING1:
            await self.one.start()
        if config.STRING2:
            await self.two.start()
        if config.STRING3:
            await self.three.start()
        if config.STRING4:
            await self.four.start()
        if config.STRING5:
            await self.five.start()

    async def decorators(self):
        @self.one.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
        @self.two.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
        @self.three.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
        @self.four.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
        @self.five.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
        async def stream_services_handler(client, update: ChatUpdate):
            await self.stop_stream(update.chat_id)

        @self.one.on_update(fl.stream_end())
        @self.two.on_update(fl.stream_end())
        @self.three.on_update(fl.stream_end())
        @self.four.on_update(fl.stream_end())
        @self.five.on_update(fl.stream_end())
        async def stream_end_handler1(client, update: StreamEnded):
            if update.stream_type != StreamEnded.Type.AUDIO:
                return
            await self.change_stream(client, update.chat_id)

        # @self.one.on_update(
        #     fl.call_participant(
        #         GroupCallParticipant.Action.JOINED | GroupCallParticipant.Action.LEFT
        #     )
        # )
        # @self.two.on_update(
        #     fl.call_participant(
        #         GroupCallParticipant.Action.JOINED | GroupCallParticipant.Action.LEFT
        #     )
        # )
        # @self.three.on_update(
        #     fl.call_participant(
        #         GroupCallParticipant.Action.JOINED | GroupCallParticipant.Action.LEFT
        #     )
        # )
        # @self.four.on_update(
        #     fl.call_participant(
        #         GroupCallParticipant.Action.JOINED | GroupCallParticipant.Action.LEFT
        #     )
        # )
        # @self.five.on_update(
        #     fl.call_participant(
        #         GroupCallParticipant.Action.JOINED | GroupCallParticipant.Action.LEFT
        #     )
        # )
        # async def participants_change_handler(
        #     client, update: UpdatedGroupCallParticipant
        # ):
        #     participant = update
        #     if participant.action not in (
        #         GroupCallParticipant.Action.JOINED,
        #         GroupCallParticipant.Action.LEFT,
        #     ):
        #         return
        #     chat_id = update.chat_id
        #     users = counter.get(chat_id)
        #     if not users:
        #         try:
        #             got = len(await client.get_participants(chat_id))
        #         except Exception:
        #             return
        #         counter[chat_id] = got
        #         if got == 1:
        #             autoend[chat_id] = datetime.now() + timedelta(minutes=AUTO_END_TIME)
        #             return
        #         autoend[chat_id] = {}
        #     else:
        #         final = (
        #             users + 1
        #             if participant.action == GroupCallParticipant.Action.JOINED
        #             else users - 1
        #         )
        #         counter[chat_id] = final
        #         if final == 1:
        #             autoend[chat_id] = datetime.now() + timedelta(minutes=AUTO_END_TIME)
        #             return
        #         autoend[chat_id] = {}


Alexa = Call()
