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
from typing import Any

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from config import BANNED_USERS
from AlexaMusic import LOGGER, app, userbot
from AlexaMusic.core.call import Alexa
from AlexaMusic.misc import sudo
from AlexaMusic.plugins import ALL_MODULES
from AlexaMusic.utils.database import get_banned_users, get_gbanned
from AlexaMusic.core.cookies import save_cookies
from AlexaMusic.core.rich_callbacks import run_rich_callback_polling


async def init() -> None:
    # Check for at least one valid Pyrogram string session
    if all(not getattr(config, f"STRING{i}") for i in range(1, 6)):
        LOGGER("AlexaMusic").error("أضف جلسة Pyrogram للحساب المساعد ثم حاول مرة أخرى.")
        exit()
    await sudo()
    try:
        for user_id in await get_gbanned():
            BANNED_USERS.add(user_id)
        for user_id in await get_banned_users():
            BANNED_USERS.add(user_id)
    except Exception:
        pass
    await app.start()
    await save_cookies()
    for module in ALL_MODULES:
        importlib.import_module(f"AlexaMusic.plugins{module}")
    LOGGER("AlexaMusic.plugins").info("Necessary Modules Imported Successfully.")

    rich_callback_task = None
    assistant_started = False
    try:
        await userbot.start()
        assistant_started = True
    except Exception as error:
        LOGGER("AlexaMusic").error(
            "فشل تشغيل الحساب المساعد: %s. "
            "سيبقى البوت متصلاً في الوضع المحدود، لكن تشغيل الموسيقى غير متاح. "
            "أعد إنشاء STRING_SESSION باستخدام genstring.py الموجود في المشروع.",
            error,
        )

    if assistant_started:
        await Alexa.start()
        try:
            await Alexa.stream_call("https://telegra.ph/file/b60b80ccb06f7a48f68b5.mp4")
        except NoActiveGroupCall:
            LOGGER("AlexaMusic").warning(
                "لم يتم العثور على محادثة صوتية فعالة أثناء فحص بدء التشغيل. "
                "سيبقى البوت متصلاً؛ افتح محادثة صوتية قبل التشغيل."
            )
        except Exception as error:
            LOGGER("AlexaMusic").warning(
                "فشل فحص المكالمة عند بدء التشغيل: %s. سيبقى البوت متصلاً.", error
            )
        await Alexa.decorators()
        LOGGER("AlexaMusic").info("تم تشغيل بوت الموسيقى بنجاح")
    else:
        LOGGER("AlexaMusic").warning(
            "تم تشغيل بوت الموسيقى في الوضع المحدود بدون حساب مساعد."
        )

    # Start Bot API polling only after the MTProto/music clients have fully
    # settled. Railway may briefly overlap old/new deployments; delaying this
    # avoids most transient getUpdates conflicts during rolling restarts.
    rich_callback_task = asyncio.create_task(
        run_rich_callback_polling(),
        name="rich-callback-polling",
    )

    await idle()

    if rich_callback_task:
        rich_callback_task.cancel()
        try:
            await rich_callback_task
        except asyncio.CancelledError:
            pass

    await app.stop()
    if assistant_started:
        await userbot.stop()
    LOGGER("AlexaMusic").info("جاري إيقاف بوت الموسيقى...")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
    LOGGER("AlexaMusic").info("تم إيقاف بوت الموسيقى")
