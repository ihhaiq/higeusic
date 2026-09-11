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

    content = str(content).strip()
    if content and not content.endswith("\n"):
        content += "\n"

    file_path = "cookies/cookies.txt"
    saved_path = await save_file(content, file_path)

    if saved_path and os.path.getsize(saved_path) > 0:
        LOGGER(__name__).info(f"Cookies saved successfully to {saved_path}.")
    else:
        LOGGER(__name__).warning(
            "Failed to save cookies. Continuing without YouTube cookies."
        )
