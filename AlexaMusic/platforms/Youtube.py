# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio
import os
import re
import json
import shlex
from typing import Union

from yt_dlp import YoutubeDL
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

import config
from AlexaMusic.utils.database import is_on_off
from AlexaMusic.utils.formatters import seconds_to_min, time_to_seconds
from AlexaMusic.logging import LOGGER


def cookiefile():
    path = os.path.join("cookies", "cookies.txt")
    return path if os.path.isfile(path) and os.path.getsize(path) > 0 else None


def cookie_args():
    path = cookiefile()
    return ["--cookies", path] if path else []


async def _yt_dlp_info(query: str):
    """Fetch one YouTube result with yt-dlp.

    Plain text is searched with ytsearch1; YouTube URLs are read directly.
    This avoids relying exclusively on youtube-search-python, which can break
    when YouTube changes its internal response format.
    """
    source = query if re.search(r"(?:youtube\.com|youtu\.be)", query) else f"ytsearch1:{query}"

    def extract():
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "cookiefile": cookiefile(),
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source, download=False)
            if isinstance(info, dict) and info.get("entries") is not None:
                entries = [item for item in (info.get("entries") or []) if item]
                if not entries:
                    raise RuntimeError("YouTube search returned no results")
                info = entries[0]
            if not isinstance(info, dict) or not info.get("id"):
                raise RuntimeError("YouTube metadata is unavailable")
            return info

    return await asyncio.to_thread(extract)


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None if offset in (None,) else text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        info = await _yt_dlp_info(link)
        title = info.get("title") or "Unknown title"
        duration_sec = int(info.get("duration") or 0)
        duration_min = seconds_to_min(duration_sec) if duration_sec else None
        thumbnail = info.get("thumbnail") or config.YOUTUBE_IMG_URL
        vidid = info["id"]
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            *cookie_args(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (1, stdout.decode().split("\n")[0]) if stdout else (0, stderr.decode())

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-i",
            "--compat-options",
            "no-youtube-unavailable-videos",
            "--get-id",
            "--flat-playlist",
            "--playlist-end",
            str(limit),
            "--skip-download",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        playlist = stdout.decode("utf-8", "replace")
        try:
            result = [key for key in playlist.split("\n") if key]
        except Exception:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        # Use yt-dlp for both direct URLs and text searches. This avoids
        # youtube-search-python parser breakages and guarantees that a direct
        # URL resolves to its exact video id.
        info = await _yt_dlp_info(link)
        title = info.get("title") or "Unknown title"
        duration = int(info.get("duration") or 0)
        duration_min = seconds_to_min(duration) if duration else None
        vidid = info["id"]
        yturl = info.get("webpage_url") or f"{self.base}{vidid}"
        thumbnail = info.get("thumbnail") or config.YOUTUBE_IMG_URL

        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
            "cookiefile": cookiefile(),
        }
        return track_details, vidid

    def ytdlp_parameters(self) -> str:
        params = ["--no-playlist", "--no-warnings"]
        path = cookiefile()
        if path:
            params.extend(["--cookies", path])
        return " ".join(shlex.quote(part) for part in params)

    def friendly_error(self, error: Exception) -> str:
        text = str(error).lower()
        if "sign in to confirm you’re not a bot" in text or "sign in to confirm you're not a bot" in text:
            return (
                "رفض YouTube جلسة الكوكيز الحالية وطلب تسجيل دخول للتحقق. "
                "حدّث COOKIES بجلسة YouTube جديدة ثم حاول مرة أخرى."
            )
        if "sign in to confirm your age" in text or "age-restricted" in text:
            return (
                "هذا الفيديو مقيّد بالعمر، والكوكيز الحالية لا تسمح لـ YouTube "
                "بالتحقق من العمر. استخدم كوكيز حساب مسجل ومسموح له بمشاهدة الفيديو."
            )
        if "video unavailable" in text or "private video" in text:
            return "فيديو YouTube غير متاح أو خاص ولا يمكن تشغيله."
        return "تعذر جلب أو تجهيز فيديو YouTube حالياً. حاول مرة أخرى بعد قليل."

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True}
        ydl = YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except Exception:
                    continue
                if "dash" not in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except Exception:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                            "cookiefile": cookiefile(),
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "cookiefile": cookiefile(),
                "format": "bestaudio[ext=m4a]/bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, False)
                xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
                if os.path.exists(xyz):
                    return xyz
                x.download([link])
                return xyz

        def video_dl():
            os.makedirs("downloads", exist_ok=True)
            ydl_optssx = {
                "cookiefile": cookiefile(),
                "format": (
                    "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/"
                    "bestvideo[height<=720]+bestaudio/"
                    "best[ext=mp4][height<=720]/best[height<=720]/best"
                ),
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "merge_output_format": "mp4",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            with YoutubeDL(ydl_optssx) as x:
                info = x.extract_info(link, download=True)
                video_id = str(info["id"])

            preferred = os.path.join("downloads", f"{video_id}.mp4")
            if os.path.isfile(preferred):
                return preferred

            for name in os.listdir("downloads"):
                if name.startswith(f"{video_id}.") and not name.endswith((".part", ".ytdl")):
                    candidate = os.path.join("downloads", name)
                    if os.path.isfile(candidate):
                        return candidate

            raise RuntimeError("yt-dlp finished but no merged video file was found")

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookiefile(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookiefile(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            if await is_on_off(config.YTDOWNLOADER):
                direct = True
                downloaded_file = await loop.run_in_executor(None, video_dl)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    *cookie_args(),
                    "-g",
                    "-f",
                    "best[ext=mp4][height<=720]/best[height<=720]/best",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode("utf-8", "replace").splitlines()[0]
                    direct = None
                else:
                    LOGGER(__name__).warning(
                        "Direct YouTube video URL unavailable; falling back to download/merge. %s",
                        stderr.decode("utf-8", "replace").strip()[-800:],
                    )
                    direct = True
                    downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            downloaded_file = await loop.run_in_executor(None, audio_dl)
        return downloaded_file, direct
