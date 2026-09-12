"""Lightweight startup diagnostics for YouTube playback dependencies."""

from __future__ import annotations

import shutil
import subprocess

import config
from AlexaMusic.logging import LOGGER
from AlexaMusic.platforms.youtube_helpers import parse_player_clients

from .cookies import cookies_file_status


def _version(command: str, *args: str) -> str | None:
    executable = shutil.which(command)
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0] if output else None


def log_youtube_health() -> None:
    logger = LOGGER(__name__)

    ytdlp_version = _version("yt-dlp", "--version")
    logger.info("YouTube health: yt-dlp version=%s", ytdlp_version or "unavailable")

    logger.info(
        "YouTube health: ffmpeg=%s",
        "available" if shutil.which("ffmpeg") else "missing",
    )

    if bool(getattr(config, "YOUTUBE_POT_ENABLED", False)):
        deno_version = _version("deno", "--version")
        logger.info(
            "YouTube health: deno=%s",
            deno_version or "missing",
        )

    logger.info(
        "YouTube health: PO provider URL=%s",
        getattr(config, "YOUTUBE_POT_PROVIDER_URL", "not configured"),
    )

    cookie_status = cookies_file_status()
    logger.info(
        "YouTube health: Cookies status=%s",
        "missing" if cookie_status == "missing" else "found",
    )

    clients = parse_player_clients(getattr(config, "YOUTUBE_PLAYER_CLIENTS", None))
    logger.info("YouTube health: player clients=%s", ",".join(clients))
