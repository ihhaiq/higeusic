# Copyright (c) 2025 @KSKOP69. All rights reserved.
# Use of this source code is governed by a proprietary license.

import os

import aiofiles

import config
from ..logging import LOGGER

DEFAULT_COOKIES_FILE = "cookies/cookies.txt"


def cookies_path() -> str:
    value = getattr(config, "YOUTUBE_COOKIES_FILE", DEFAULT_COOKIES_FILE)
    try:
        path = os.fspath(value).strip()
    except (TypeError, ValueError):
        path = ""
    return path or DEFAULT_COOKIES_FILE


def _normalize_cookies(content: object) -> str:
    text = str(content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1].strip()
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def cookies_format_looks_valid(content: str) -> bool:
    lines = content.splitlines()
    if not lines:
        return False
    first_line = lines[0].lstrip("\ufeff")
    if first_line not in {"# Netscape HTTP Cookie File", "# HTTP Cookie File"}:
        return False

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain = parts[0].lstrip(".").lower()
        if domain.endswith("youtube.com") or domain.endswith("google.com"):
            return True
    return False


def cookies_file_status() -> str:
    path = cookies_path()
    try:
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            return "missing"
        with open(path, "r", encoding="utf-8", errors="replace") as file:
            content = file.read()
    except OSError:
        return "missing"
    return "valid" if cookies_format_looks_valid(content) else "invalid"


async def save_file(content: str, file_path: str) -> str:
    try:
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        async with aiofiles.open(file_path, "w", encoding="utf-8") as file:
            await file.write(content)
        return file_path
    except OSError:
        return ""


async def save_cookies():
    path = cookies_path()
    env_content = getattr(config, "COOKIES", None)

    if env_content:
        content = _normalize_cookies(env_content)
        saved_path = await save_file(content, path)
        if not saved_path:
            LOGGER(__name__).warning("Cookies missing")
            return
    else:
        try:
            if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                LOGGER(__name__).warning("Cookies missing")
                return
            async with aiofiles.open(path, "r", encoding="utf-8", errors="replace") as file:
                content = await file.read()
        except OSError:
            LOGGER(__name__).warning("Cookies missing")
            return

    LOGGER(__name__).info("Cookies file found")
    if cookies_format_looks_valid(content):
        LOGGER(__name__).info("Cookies format looks valid")
    else:
        LOGGER(__name__).warning("Cookies appear expired/rejected")
