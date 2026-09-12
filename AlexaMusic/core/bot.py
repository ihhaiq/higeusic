# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio
import sys

from pyrogram import Client
from pyrogram.errors import FloodWait
import config
from ..logging import LOGGER
from pyrogram.enums import ChatMemberStatus


class AlexaBot(Client):
    def __init__(self):
        super().__init__(
            "MusicBot",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            max_concurrent_transmissions=5,
        )
        LOGGER(__name__).info("Starting Bot...")

    async def start(self):
        while True:
            try:
                await super().start()
                break
            except FloodWait as error:
                wait_seconds = int(getattr(error, "value", 30))
                LOGGER(__name__).warning(
                    f"Telegram فرض انتظاراً لمدة {wait_seconds} ثانية قبل إعادة تسجيل دخول البوت. "
                    "سيبقى السيرفر يعمل وينتظر تلقائياً بدون إعادة تشغيل متكررة."
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
        try:
            await self.get_chat(config.LOG_GROUP_ID)
        except Exception:
            LOGGER(__name__).error(
                "فشل البوت في الوصول إلى مجموعة السجل. أضف البوت إليها وارفعه مشرفاً."
            )
            sys.exit()
        a = await self.get_chat_member(config.LOG_GROUP_ID, self.id)
        if a.status != ChatMemberStatus.ADMINISTRATOR:
            LOGGER(__name__).error("يرجى رفع البوت مشرفاً في مجموعة السجل.")
            sys.exit()
        if get_me.last_name:
            self.name = f"{get_me.first_name} {get_me.last_name}"
        else:
            self.name = get_me.first_name
        LOGGER(__name__).info(f"بدأ بوت الموسيقى باسم {self.name}")
