# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >

"""YouTube lookup, streaming URL extraction, and optional media downloads.

All yt-dlp operations use the same isolated fallback order:
PO Token player-client fallbacks -> Cookies-only -> anonymous.
No per-chat state is stored here, so concurrent calls cannot change each
other's authentication mode or queue state.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Union

from pyrogram.enums import MessageEntityType
from pyrogram.types import Message

import config
from AlexaMusic.logging import LOGGER
from AlexaMusic.platforms.youtube_helpers import (
    YouTubeAttempt,
    YouTubeAuthStrategy,
    build_attempts,
    classify_youtube_error,
    cookie_file_available,
    extraction_source,
    friendly_youtube_error,
    is_youtube_url,
    parse_player_clients,
)
from AlexaMusic.utils.database import is_on_off
from AlexaMusic.utils.formatters import seconds_to_min


class YouTubeExtractionError(RuntimeError):
    def __init__(self, errors: list[tuple[YouTubeAttempt, Exception]]):
        self.errors = errors
        last_error = errors[-1][1] if errors else RuntimeError("YouTube extraction failed")
        super().__init__(friendly_youtube_error(last_error))


def cookiefile() -> str | None:
    path = getattr(config, "YOUTUBE_COOKIES_FILE", "cookies/cookies.txt")
    return os.fspath(path) if cookie_file_available(path) else None


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def is_youtube_url(self, value: str) -> bool:
        return is_youtube_url(value)

    def stream_attempts(self) -> tuple[YouTubeAttempt, ...]:
        return build_attempts(
            pot_enabled=bool(config.YOUTUBE_POT_ENABLED),
            has_cookies=bool(cookiefile()),
            player_clients=parse_player_clients(
                getattr(config, "YOUTUBE_PLAYER_CLIENTS", None)
            ),
        )

    def _attempt_args(self, attempt: YouTubeAttempt) -> list[str]:
        path = cookiefile()

        if attempt.strategy is YouTubeAuthStrategy.PO_TOKEN:
            client = attempt.player_client or "mweb"
            return [
                "--extractor-args",
                f"youtubepot-bgutilhttp:base_url={config.YOUTUBE_POT_PROVIDER_URL}",
                "--extractor-args",
                f"youtube:player_client={client}",
            ]

        args = ["--no-plugin-dirs"]
        if attempt.strategy is YouTubeAuthStrategy.COOKIES:
            if not path:
                raise RuntimeError("Cookies missing")
            args.extend(
                [
                    "--cookies",
                    path,
                    "--extractor-args",
                    "youtube:player_client=default,web_embedded",
                ]
            )
        return args

    def log_attempt(self, attempt: YouTubeAttempt, *, operation: str, chat_id=None):
        chat_context = f" chat_id={chat_id}" if chat_id is not None else ""
        if attempt.strategy is YouTubeAuthStrategy.PO_TOKEN:
            LOGGER(__name__).info(
                "Using PO Token operation=%s client=%s%s",
                operation,
                attempt.player_client or "mweb",
                chat_context,
            )
        elif attempt.strategy is YouTubeAuthStrategy.COOKIES:
            LOGGER(__name__).info("Using Cookies operation=%s%s", operation, chat_context)
        else:
            LOGGER(__name__).info(
                "Retrying without Cookies (Anonymous) operation=%s%s",
                operation,
                chat_context,
            )

    def log_failure(
        self,
        attempt: YouTubeAttempt,
        error: object,
        *,
        operation: str,
        chat_id=None,
    ):
        chat_context = f" chat_id={chat_id}" if chat_id is not None else ""
        category = classify_youtube_error(error)
        detail = str(error).replace("\n", " ")[-500:]
        if attempt.strategy is YouTubeAuthStrategy.PO_TOKEN:
            LOGGER(__name__).warning(
                "PO Token failed operation=%s client=%s%s category=%s: %s",
                operation,
                attempt.player_client or "mweb",
                chat_context,
                category,
                detail,
            )
        elif attempt.strategy is YouTubeAuthStrategy.COOKIES:
            label = (
                "Cookies appear expired/rejected"
                if category == "cookies_rejected"
                else "Cookies failed"
            )
            LOGGER(__name__).warning(
                "%s operation=%s%s category=%s: %s",
                label,
                operation,
                chat_context,
                category,
                detail,
            )
        else:
            LOGGER(__name__).warning(
                "Anonymous YouTube attempt failed operation=%s%s category=%s: %s",
                operation,
                chat_context,
                category,
                detail,
            )

    async def _run_process(
        self,
        args: list[str],
        *,
        timeout: int | None = None,
    ) -> tuple[str, str]:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        wait_seconds = timeout or config.YOUTUBE_EXTRACT_TIMEOUT
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=wait_seconds
            )
        except asyncio.CancelledError:
            proc.kill()
            await proc.communicate()
            raise
        except asyncio.TimeoutError as error:
            proc.kill()
            await proc.communicate()
            raise RuntimeError(
                f"yt-dlp timed out after {wait_seconds} seconds"
            ) from error
        output = stdout.decode("utf-8", "replace").strip()
        errors = stderr.decode("utf-8", "replace").strip()
        if proc.returncode != 0:
            raise RuntimeError(
                errors or output or f"yt-dlp exited with status {proc.returncode}"
            )
        return output, errors

    async def _run_with_fallback(
        self,
        base_args: list[str],
        *,
        operation: str,
        timeout: int | None = None,
    ) -> str:
        errors: list[tuple[YouTubeAttempt, Exception]] = []
        seen_configs: set[tuple[str, ...]] = set()
        for attempt in self.stream_attempts():
            try:
                attempt_args = self._attempt_args(attempt)
            except Exception as error:
                errors.append((attempt, error))
                self.log_failure(attempt, error, operation=operation)
                continue

            config_key = tuple(attempt_args)
            if config_key in seen_configs:
                continue
            seen_configs.add(config_key)

            self.log_attempt(attempt, operation=operation)
            args = [
                "--ignore-config",
                "--no-warnings",
                *attempt_args,
                *base_args,
            ]
            try:
                output, _ = await self._run_process(args, timeout=timeout)
                return output
            except Exception as error:
                errors.append((attempt, error))
                self.log_failure(attempt, error, operation=operation)
        raise YouTubeExtractionError(errors)

    async def _extract_info(self, query: str, *, search_limit: int = 1) -> dict:
        source = extraction_source(query, search_limit)
        is_search = source.startswith("ytsearch")
        args = ["--skip-download", "--dump-single-json"]
        if is_search:
            args.extend(["--flat-playlist", "--playlist-end", str(search_limit)])
        else:
            args.append("--no-playlist")
        args.append(source)
        raw = await self._run_with_fallback(args, operation="metadata")
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError("yt-dlp returned invalid metadata JSON") from error
        if not isinstance(info, dict):
            raise RuntimeError("YouTube metadata is unavailable")
        return info

    @staticmethod
    def _first_entry(info: dict) -> dict:
        if info.get("entries") is None:
            return info
        entry = next((item for item in info.get("entries") or [] if item), None)
        if not isinstance(entry, dict):
            raise RuntimeError("YouTube search returned no results")
        return entry

    @staticmethod
    def _thumbnail(info: dict) -> str:
        if info.get("thumbnail"):
            return info["thumbnail"]
        thumbnails = [item for item in info.get("thumbnails") or [] if item.get("url")]
        return thumbnails[-1]["url"] if thumbnails else config.YOUTUBE_IMG_URL

    async def info(self, link: str, videoid: Union[bool, str] = None) -> dict:
        if videoid:
            link = self.base + link
        return self._first_entry(await self._extract_info(link))

    async def search_many(self, query: str, limit: int = 10) -> list[dict]:
        info = await self._extract_info(query, search_limit=limit)
        entries = info.get("entries") if isinstance(info, dict) else None
        if entries is None:
            entries = [info]
        return [
            entry for entry in entries if isinstance(entry, dict) and entry.get("id")
        ]

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return self.is_youtube_url(link)

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            text = message.text or message.caption or ""
            entities = [
                *(message.entities or []),
                *(message.caption_entities or []),
            ]
            for entity in entities:
                if entity.type == MessageEntityType.TEXT_LINK:
                    return entity.url
                if entity.type == MessageEntityType.URL:
                    return text[entity.offset : entity.offset + entity.length]
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        info = await self.info(link, videoid)
        title = info.get("title") or "Unknown title"
        duration_sec = int(info.get("duration") or 0)
        duration_min = seconds_to_min(duration_sec) if duration_sec else None
        thumbnail = self._thumbnail(info)
        return title, duration_min, duration_sec, thumbnail, info["id"]

    async def title(self, link: str, videoid: Union[bool, str] = None):
        return (await self.info(link, videoid)).get("title") or "Unknown title"

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        duration = int((await self.info(link, videoid)).get("duration") or 0)
        return seconds_to_min(duration) if duration else None

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        return self._thumbnail(await self.info(link, videoid))

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        try:
            output = await self._run_with_fallback(
                ["-g", "-f", "best[height<=?720][width<=?1280]/best", link],
                operation="direct-video-url",
            )
        except Exception as error:
            return 0, str(error)
        url = next((line for line in output.splitlines() if line.strip()), "")
        if not url:
            return 0, "yt-dlp returned no playable video URL"
        LOGGER(__name__).info("Streaming directly from YouTube")
        return 1, url

    async def resolve_stream(
        self,
        link: str,
        attempt: YouTubeAttempt,
        *,
        video: bool,
        max_height: int = 720,
    ) -> tuple[str, str | None]:
        """Resolve expiring Google media URLs for one isolated auth attempt.

        Video playback prefers a single progressive stream containing both
        audio and video.  PyTgCalls can then read both tracks from the same
        input, which is more reliable than two independent Googlevideo URLs.
        If YouTube does not expose a muxed format, fall back to an explicit
        video-only + audio-only pair.  A video-only URL is never accepted as
        a successful video result.
        """
        attempt_args = self._attempt_args(attempt)

        if not video:
            args = [
                "--ignore-config",
                "--no-warnings",
                *attempt_args,
                "--no-playlist",
                "-g",
                "-f",
                "bestaudio/best",
                link,
            ]
            output, _ = await self._run_process(args)
            urls = [line.strip() for line in output.splitlines() if line.strip()]
            if not urls:
                raise RuntimeError("yt-dlp returned no playable audio stream URL")
            return urls[0], None

        height = max(144, int(max_height or 720))
        selectors = (
            (
                f"best[acodec!=none][vcodec!=none][height<={height}]/"
                "best[acodec!=none][vcodec!=none]"
            ),
            (
                f"bestvideo[vcodec~='(vp09|avc1)'][height<={height}]"
                "+bestaudio[ext=m4a]/"
                f"bestvideo[height<={height}]+bestaudio"
            ),
        )
        errors: list[Exception] = []

        for selector in selectors:
            args = [
                "--ignore-config",
                "--no-warnings",
                *attempt_args,
                "--no-playlist",
                "-g",
                "-f",
                selector,
                link,
            ]
            try:
                output, _ = await self._run_process(args)
            except Exception as error:
                errors.append(error)
                continue

            urls = [line.strip() for line in output.splitlines() if line.strip()]
            if len(urls) == 1:
                LOGGER(__name__).info(
                    "Resolved YouTube video as a combined audio/video stream"
                )
                return urls[0], None
            if len(urls) >= 2:
                LOGGER(__name__).info(
                    "Resolved YouTube video as separate video + audio streams"
                )
                return urls[0], urls[1]

            errors.append(RuntimeError("yt-dlp returned no playable video stream URL"))

        if errors:
            raise errors[-1]
        raise RuntimeError("yt-dlp returned no playable video stream URL")

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        output = await self._run_with_fallback(
            [
                "--ignore-errors",
                "--compat-options",
                "no-youtube-unavailable-videos",
                "--get-id",
                "--flat-playlist",
                "--playlist-end",
                str(limit),
                "--skip-download",
                link,
            ],
            operation="playlist",
        )
        return [item for item in output.splitlines() if item]

    async def track(self, link: str, videoid: Union[bool, str] = None):
        info = await self.info(link, videoid)
        title = info.get("title") or "Unknown title"
        duration = int(info.get("duration") or 0)
        duration_min = seconds_to_min(duration) if duration else None
        vidid = info["id"]
        yturl = info.get("webpage_url") or info.get("url") or f"{self.base}{vidid}"
        if not self.is_youtube_url(yturl):
            yturl = f"{self.base}{vidid}"
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": self._thumbnail(info),
            "cookiefile": cookiefile(),
        }
        return track_details, vidid

    def friendly_error(self, error: object) -> str:
        return friendly_youtube_error(error)

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        info = await self.info(link, videoid)
        formats_available = []
        for item in info.get("formats") or []:
            if "dash" in str(item.get("format", "")).lower():
                continue
            if not item.get("format_id") or not item.get("ext"):
                continue
            formats_available.append(
                {
                    "format": item.get("format", ""),
                    "filesize": item.get("filesize") or item.get("filesize_approx"),
                    "format_id": item["format_id"],
                    "ext": item["ext"],
                    "format_note": item.get("format_note")
                    or item.get("resolution")
                    or "unknown",
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
        results = await self.search_many(link, limit=10)
        if not 0 <= query_type < len(results):
            raise RuntimeError("YouTube search result index is unavailable")
        result = results[query_type]
        duration = int(result.get("duration") or 0)
        return (
            result.get("title") or "Unknown title",
            seconds_to_min(duration) if duration else None,
            self._thumbnail(result),
            result["id"],
        )

    async def _download_file(
        self,
        link: str,
        *,
        format_selector: str,
        outtmpl: str,
        merge_format: str | None = None,
        extract_audio: bool = False,
    ) -> str:
        Path("downloads").mkdir(parents=True, exist_ok=True)
        args = [
            "--no-playlist",
            "--format",
            format_selector,
            "--output",
            outtmpl,
            "--print",
            "after_move:filepath",
        ]
        if merge_format:
            args.extend(["--merge-output-format", merge_format])
        if extract_audio:
            args.extend(
                ["--extract-audio", "--audio-format", "mp3", "--audio-quality", "192K"]
            )
        args.append(link)
        output = await self._run_with_fallback(
            args,
            operation="download",
            timeout=max(config.YOUTUBE_EXTRACT_TIMEOUT, 900),
        )
        path = next(
            (line.strip() for line in reversed(output.splitlines()) if line.strip()), ""
        )
        if not path or not os.path.isfile(path):
            raise RuntimeError("yt-dlp completed but the downloaded file was not found")
        return path

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
        safe_title = re.sub(
            r"[^\w .()-]+", " ", str(title or "youtube"), flags=re.UNICODE
        ).strip()
        safe_title = safe_title[:120] or "youtube"

        if songvideo:
            return await self._download_file(
                link,
                format_selector=f"{format_id}+140",
                outtmpl=f"downloads/{safe_title}.%(ext)s",
                merge_format="mp4",
            )
        if songaudio:
            return await self._download_file(
                link,
                format_selector=str(format_id),
                outtmpl=f"downloads/{safe_title}.%(ext)s",
                extract_audio=True,
            )
        if video:
            if not await is_on_off(config.YTDOWNLOADER):
                ok, direct_url = await self.video(link)
                if ok:
                    return direct_url, None
                LOGGER(__name__).warning(
                    "Direct YouTube video URL unavailable; falling back to download/merge: %s",
                    direct_url[-500:],
                )
            path = await self._download_file(
                link,
                format_selector=(
                    "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/"
                    "bestvideo[height<=720]+bestaudio/best[ext=mp4][height<=720]/"
                    "best[height<=720]/best"
                ),
                outtmpl="downloads/%(id)s.%(ext)s",
                merge_format="mp4",
            )
            return path, True
        path = await self._download_file(
            link,
            format_selector="bestaudio[ext=m4a]/bestaudio/best",
            outtmpl="downloads/%(id)s.%(ext)s",
        )
        return path, True
