# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import random

from AlexaMusic import userbot
from AlexaMusic.core.mongo import mongodb
from AlexaMusic.utils.exceptions import AssistantErr

db = mongodb.assistants
assistantdict = {}

_ASSISTANT_ATTRS = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
}


def _available_assistants():
    from AlexaMusic.core.userbot import assistants

    if not assistants:
        raise AssistantErr(
            "لا يوجد حساب مساعد فعّال. أصلح STRING_SESSION ثم أعد نشر البوت."
        )
    return assistants


async def get_client(assistant: int):
    attr = _ASSISTANT_ATTRS.get(int(assistant))
    return getattr(userbot, attr, None) if attr else None


async def set_assistant(chat_id):
    ran_assistant = random.choice(_available_assistants())
    assistantdict[chat_id] = ran_assistant
    await db.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    return await get_client(ran_assistant)


async def get_assistant(chat_id: int):
    assistants = _available_assistants()
    assistant = assistantdict.get(chat_id)

    if assistant in assistants:
        return await get_client(assistant)

    dbassistant = await db.find_one({"chat_id": chat_id})
    if dbassistant:
        stored = dbassistant.get("assistant")
        if stored in assistants:
            assistantdict[chat_id] = stored
            return await get_client(stored)

    return await set_assistant(chat_id)


async def set_calls_assistant(chat_id):
    ran_assistant = random.choice(_available_assistants())
    assistantdict[chat_id] = ran_assistant
    await db.update_one(
        {"chat_id": chat_id},
        {"$set": {"assistant": ran_assistant}},
        upsert=True,
    )
    return ran_assistant


async def group_assistant(self, chat_id: int):
    assistants = _available_assistants()
    assistant = assistantdict.get(chat_id)

    if assistant not in assistants:
        dbassistant = await db.find_one({"chat_id": chat_id})
        stored = dbassistant.get("assistant") if dbassistant else None
        if stored in assistants:
            assistant = stored
            assistantdict[chat_id] = stored
        else:
            assistant = await set_calls_assistant(chat_id)

    attr = _ASSISTANT_ATTRS.get(int(assistant))
    if not attr:
        raise AssistantErr("تعذر تحديد الحساب المساعد لهذا التشغيل.")
    return getattr(self, attr)
