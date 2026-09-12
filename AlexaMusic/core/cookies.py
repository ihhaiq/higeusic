# Copyright (c) 2025 @KSKOP69. All rights reserved.
# Use of this source code is governed by a proprietary license.

import os

import aiofiles

import config
from ..logging import LOGGER


async def save_file(content: str, file_path: str):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
            await file.write(content)
        return file_path
    except Exception as e:
        LOGGER(__name__).error(f"Error saving file {file_path}: {e}")
        return ""


async def save_cookies():
    content = config.COOKIES

    if not content:
        LOGGER(__name__).warning(
            "COOKIES is not configured. Continuing without YouTube cookies."
        )
        return

    content = str(content).replace("\r\n", "\n").replace("\r", "\n").strip()

    # Railway users sometimes paste the entire value wrapped in quotes.
    if len(content) >= 2 and content[0] == content[-1] and content[0] in {'"', "'"}:
        content = content[1:-1].strip()

    if content and not content.endswith("\n"):
        content += "\n"

    first_line = content.splitlines()[0].lstrip("\ufeff") if content else ""
    valid_header = first_line in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}

    cookie_names = set()
    youtube_rows = 0
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            domain = parts[0].lstrip(".").lower()
            if domain.endswith("youtube.com") or domain.endswith("google.com"):
                youtube_rows += 1
                cookie_names.add(parts[5])

    auth_names = {
        "SID",
        "HSID",
        "SSID",
        "APISID",
        "SAPISID",
        "__Secure-1PAPISID",
        "__Secure-3PAPISID",
        "__Secure-1PSID",
        "__Secure-3PSID",
        "LOGIN_INFO",
    }
    auth_count = len(cookie_names & auth_names)

    if not valid_header:
        LOGGER(__name__).warning(
            "COOKIES does not start with a valid Netscape cookie header. "
            "yt-dlp may ignore or reject it."
        )
    elif youtube_rows == 0:
        LOGGER(__name__).warning(
            "COOKIES has a Netscape header but contains no YouTube/Google cookie rows."
        )
    elif auth_count == 0:
        LOGGER(__name__).warning(
            "COOKIES contains YouTube/Google rows but no recognizable signed-in "
            "account cookies. Export cookies while logged in to YouTube."
        )
    else:
        LOGGER(__name__).info(
            f"Cookie format check passed: {youtube_rows} YouTube/Google rows, "
            f"{auth_count} authentication-cookie names detected."
        )

    file_path = "cookies/cookies.txt"
    saved_path = await save_file(content, file_path)

    if saved_path and os.path.getsize(saved_path) > 0:
        LOGGER(__name__).info(f"Cookies saved successfully to {saved_path}.")
    else:
        LOGGER(__name__).warning(
            "Failed to save cookies. Continuing without YouTube cookies."
        )
