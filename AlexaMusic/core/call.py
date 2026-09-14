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
import os
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
from AlexaMusic.core.telegram_media_fallback import (
    fetch_media_from_telegram_bot,
    route_telegram_media_fallback_reply,
)
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
from AlexaMusic.utils.playback_progress import run_with_progress
from AlexaMusic.utils.rich_stream import send_stream_rich_message
from AlexaMusic.utils.stream.autoclear import auto_clean
from AlexaMusic.utils.thumbnails import gen_thumb
from strings import get_string

autoend = {}
counter = {}
AUTO_END_TIME = 1


@app.on_message(group=-100)
async def telegram_media_fallback_reply_handler(_, message):
    """Receive external downloader replies without bot-forbidden history calls."""
    route_telegram_media_fallback_reply(message)


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
    allow_local_fallback=False,
    fallback_client=None,
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
        if video and audio_link and allow_local_fallback:
            # PyTgCalls can accept separate DASH inputs without raising while
            # only the video track reaches Telegram.  For finite videos, skip
            # that silent-success path and let yt-dlp merge both tracks into a
            # temporary file below.
            errors.append(
                RuntimeError("Separate YouTube audio/video streams require local merging")
            )
            LOGGER(__name__).warning(
                "Separate YouTube A/V streams detected; using local merge "
                "chat_id=%s strategy=%s",
                chat_id,
                attempt.strategy.value,
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
            return None
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

    if youtube and allow_local_fallback:
        media_kind = "video" if video else "audio"
        media_label = "الفيديو" if video else "الصوت"

        async def play_downloaded_file(path):
            stream = _media_stream(
                path,
                audio_quality=audio_quality,
                video_quality=video_quality,
                video=video,
                strict=True,
            )
            kwargs = {"config": group_config} if group_config is not None else {}
            await player.play(chat_id, stream, **kwargs)

        LOGGER(__name__).warning(
            "Direct YouTube %s streaming failed; downloading a temporary file chat_id=%s",
            media_kind,
            chat_id,
        )
        local_path = None
        try:
            if video:
                local_path = await YouTube.download_stream_video(
                    link,
                    chat_id=chat_id,
                )
            else:
                local_path = await YouTube.download_stream_audio(
                    link,
                    chat_id=chat_id,
                )
        except Exception as error:
            errors.append(error)
            LOGGER(__name__).warning(
                "Local YouTube %s download failed chat_id=%s: %s",
                media_kind,
                chat_id,
                str(error).replace("\n", " ")[-500:],
            )

        if local_path:
            try:
                await play_downloaded_file(local_path)
                LOGGER(__name__).info(
                    "Streaming YouTube %s from temporary file chat_id=%s path=%s",
                    media_kind,
                    chat_id,
                    local_path,
                )
                return local_path
            except Exception as error:
                errors.append(error)
                with contextlib.suppress(Exception):
                    os.remove(local_path)
                LOGGER(__name__).warning(
                    "Downloaded YouTube %s could not be played chat_id=%s: %s",
                    media_kind,
                    chat_id,
                    str(error).replace("\n", " ")[-500:],
                )

        external_enabled = bool(
            getattr(config, "TELEGRAM_MEDIA_FALLBACK_ENABLED", False)
        )
        external_chat_id = int(
            getattr(config, "TELEGRAM_MEDIA_FALLBACK_CHAT_ID", 0) or 0
        )
        external_bot = str(
            getattr(config, "TELEGRAM_MEDIA_FALLBACK_BOT", "") or ""
        ).strip()

        if external_enabled:
            if fallback_client is None or not external_chat_id or not external_bot:
                raise AssistantErr(
                    "مسار بوت التحميل الخارجي مفعّل، لكن إعداداته ناقصة. "
                    "تحقق من TELEGRAM_MEDIA_FALLBACK_CHAT_ID و"
                    "TELEGRAM_MEDIA_FALLBACK_BOT."
                )

            command = (
                getattr(config, "TELEGRAM_MEDIA_FALLBACK_VIDEO_COMMAND", "/v")
                if video
                else getattr(config, "TELEGRAM_MEDIA_FALLBACK_AUDIO_COMMAND", "/d")
            )
            LOGGER(__name__).warning(
                "Using external Telegram downloader as final fallback "
                "chat_id=%s mode=%s source_chat_id=%s",
                chat_id,
                media_kind,
                external_chat_id,
            )
            external_path = None
            try:
                external_path = await fetch_media_from_telegram_bot(
                    fallback_client,
                    source_chat_id=external_chat_id,
                    bot_username=external_bot,
                    command=command,
                    link=link,
                    request_chat_id=chat_id,
                    response_timeout=getattr(
                        config,
                        "TELEGRAM_MEDIA_FALLBACK_RESPONSE_TIMEOUT",
                        180,
                    ),
                    download_timeout=getattr(
                        config,
                        "TELEGRAM_MEDIA_FALLBACK_DOWNLOAD_TIMEOUT",
                        900,
                    ),
                    cleanup=getattr(
                        config,
                        "TELEGRAM_MEDIA_FALLBACK_CLEANUP",
                        True,
                    ),
                )
                await play_downloaded_file(external_path)
                LOGGER(__name__).info(
                    "Streaming YouTube %s from external Telegram fallback "
                    "chat_id=%s path=%s",
                    media_kind,
                    chat_id,
                    external_path,
                )
                return external_path
            except Exception as error:
                errors.append(error)
                if external_path:
                    with contextlib.suppress(Exception):
                        os.remove(external_path)
                raise AssistantErr(
                    "فشلت جميع مسارات YouTube والتنزيل المحلي، ثم فشل "
                    f"بوت التحميل الخارجي أيضاً في توفير {media_label}. "
                    f"التفاصيل: {str(error).replace(chr(10), ' ')[-400:]}"
                ) from error

        detail = YouTube.friendly_error(errors[-1]) if errors else "سبب غير معروف"
        raise AssistantErr(
            f"رفض YouTube روابط بث {media_label} المباشرة، ثم فشل البوت أيضاً "
            f"في تنزيل نسخة مؤقتة من {media_label}. "
            f"تفاصيل السبب: {detail}"
        )

    if errors:
        raise AssistantErr(YouTube.friendly_error(errors[-1]))
    raise AssistantErr("تعذر العثور على مسار وسائط صالح للتشغيل.")


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
                local_file = await _play_media_with_fallback(
                    assistant,
                    chat_id,
                    link,
                    audio_quality=audio_stream_quality,
                    video_quality=video_stream_quality,
                    video=bool(video),
                    image=image,
                    group_config=ksk,
                    allow_local_fallback=duration_to_seconds(duration) > 0,
                    fallback_client=app,
                )
                break
            except ChatAdminRequired:
                raise AssistantErr(
                    "تعذر على الحساب المساعد الانضمام إلى المحادثة الصوتية. "
                    "تأكد أنه عضو وغير محظور؛ لا يحتاج أن يكون مشرفاً."
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
        return local_file
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
                    local_file = await run_with_progress(
                        mystic,
                        _play_media_with_fallback(
                            client,
                            chat_id,
                            file_path,
                            audio_quality=audio_stream_quality,
                            video_quality=video_stream_quality,
                            video=video,
                            image=image,
                            allow_local_fallback=True,
                            fallback_client=app,
                        ),
                        video=video,
                    )
                    if local_file:
                        check[0]["file"] = local_file
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
