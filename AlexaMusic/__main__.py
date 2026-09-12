# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio
import importlib

from pyrogram import idle

from config import BANNED_USERS
from AlexaMusic import LOGGER, app, userbot
from AlexaMusic.core.call import Alexa
from AlexaMusic.core.cookies import save_cookies
from AlexaMusic.misc import sudo
from AlexaMusic.plugins import ALL_MODULES
from AlexaMusic.utils.database import get_banned_users, get_gbanned


async def init() -> None:
    await sudo()
    try:
        for user_id in await get_gbanned():
            BANNED_USERS.add(user_id)
        for user_id in await get_banned_users():
            BANNED_USERS.add(user_id)
    except Exception as error:
        LOGGER("AlexaMusic").warning(
            "تعذر تحميل قوائم الحظر عند بدء التشغيل: %s",
            type(error).__name__,
        )

    await app.start()
    await save_cookies()

    for module in ALL_MODULES:
        importlib.import_module(f"AlexaMusic.plugins{module}")
    LOGGER("AlexaMusic.plugins").info("تم تحميل وحدات البوت بنجاح.")

    userbot_started = False
    playback_started = False
    try:
        assistant_count = await userbot.start()
        userbot_started = True
        await Alexa.start()
        await Alexa.decorators()
        playback_started = True
        LOGGER("AlexaMusic").info(
            "تم تشغيل نظام الموسيقى بنجاح باستخدام %s حساب مساعد.",
            assistant_count,
        )
    except Exception as error:
        LOGGER("AlexaMusic").error(
            "تعذر تشغيل نظام المساعد: %s. "
            "سيبقى البوت متصلاً في الوضع المحدود، لكن تشغيل الموسيقى غير متاح. "
            "تحقق من STRING_SESSION وأنشئها باستخدام genstring.py إذا لزم الأمر.",
            error,
        )

    if not playback_started:
        LOGGER("AlexaMusic").warning(
            "تم تشغيل البوت في الوضع المحدود بدون نظام تشغيل صوتي فعّال."
        )

    try:
        await idle()
    finally:
        await app.stop()
        if userbot_started:
            await userbot.stop()
        LOGGER("AlexaMusic").info("تم إيقاف بوت الموسيقى.")


if __name__ == "__main__":
    asyncio.run(init())
