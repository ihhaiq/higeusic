# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio

from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait

import config
from ..logging import LOGGER


class AlexaBot(Client):
    def __init__(self):
        super().__init__(
            "MusicBot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            max_concurrent_transmissions=5,
        )
        LOGGER(__name__).info("جاري تشغيل البوت...")

    async def start(self):
        while True:
            try:
                await super().start()
                break
            except FloodWait as error:
                wait_seconds = int(getattr(error, "value", 30))
                LOGGER(__name__).warning(
                    "Telegram فرض انتظاراً لمدة %s ثانية قبل إعادة تسجيل دخول البوت. "
                    "سيبقى السيرفر يعمل وينتظر تلقائياً بدون إعادة تشغيل متكررة.",
                    wait_seconds,
                )
                try:
                    await self.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(wait_seconds + 5)

        get_me = await self.get_me()
        self.username = get_me.username
        self.id = get_me.id
        self.mention = get_me.mention
        self.name = (
            f"{get_me.first_name} {get_me.last_name}"
            if get_me.last_name
            else get_me.first_name
        )

        try:
            member = await self.get_chat_member(config.LOG_GROUP_ID, self.id)
            if member.status != ChatMemberStatus.ADMINISTRATOR:
                LOGGER(__name__).warning(
                    "البوت ليس مشرفاً في مجموعة السجل. سيستمر التشغيل بدون إيقاف الخدمة."
                )
        except Exception as error:
            LOGGER(__name__).warning(
                "تعذر التحقق من مجموعة السجل (%s). سيستمر تشغيل البوت.",
                type(error).__name__,
            )

        LOGGER(__name__).info("بدأ بوت الموسيقى باسم %s", self.name)
