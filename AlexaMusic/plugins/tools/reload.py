# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio

from pyrogram import filters
from pyrogram.enums import ChatMembersFilter
from pyrogram.types import CallbackQuery, Message

from config import BANNED_USERS, MUSIC_BOT_NAME, adminlist, lyrical
from strings import get_command
from AlexaMusic import app
from AlexaMusic.core.call import Alexa
from AlexaMusic.misc import db
from AlexaMusic.utils.database import get_authuser_names, get_cmode
from AlexaMusic.utils.decorators import ActualAdminCB, AdminActual, language
from AlexaMusic.utils.formatters import alpha_to_int

### Multi-Lang Commands
RELOAD_COMMAND = get_command("RELOAD_COMMAND")
RESTART_COMMAND = get_command("RESTART_COMMAND")


@app.on_message(filters.command(RELOAD_COMMAND) & filters.group & ~BANNED_USERS)
@language
async def reload_admin_cache(client, message: Message, _):
    try:
        chat_id = message.chat.id
        admins = app.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS)
        authusers = await get_authuser_names(chat_id)
        adminlist[chat_id] = []
        async for user in admins:
            if user.privileges.can_manage_video_chats:
                adminlist[chat_id].append(user.user.id)
        for user in authusers:
            user_id = await alpha_to_int(user)
            adminlist[chat_id].append(user_id)
        await message.reply_text(_["admin_20"])
    except Exception:
        await message.reply_text(
            "تعذر تحديث قائمة المشرفين. تأكد من أن البوت مشرف ولديه الصلاحيات المطلوبة."
        )


@app.on_message(filters.command(RESTART_COMMAND) & filters.group & ~BANNED_USERS)
@AdminActual
async def restartbot(client, message: Message, _):
    mystic = await message.reply_text(
        f"يرجى الانتظار، جاري إعادة تهيئة {MUSIC_BOT_NAME} لهذه المحادثة..."
    )
    await asyncio.sleep(1)
    try:
        db[message.chat.id] = []
        await Alexa.stop_stream(message.chat.id)
    except Exception:
        pass
    chat_id = await get_cmode(message.chat.id)
    if chat_id:
        try:
            await app.get_chat(chat_id)
        except Exception:
            pass
        try:
            db[chat_id] = []
            await Alexa.stop_stream(chat_id)
        except Exception:
            pass
    return await mystic.edit_text(
        f"تمت إعادة تهيئة {MUSIC_BOT_NAME} لهذه المحادثة، ويمكنك بدء التشغيل من جديد."
    )


@app.on_callback_query(filters.regex("close") & ~BANNED_USERS)
async def close_menu(_, CallbackQuery):
    try:
        await CallbackQuery.message.delete()
        await CallbackQuery.answer()
    except Exception:
        return


@app.on_callback_query(filters.regex("stop_downloading") & ~BANNED_USERS)
@ActualAdminCB
async def stop_download(client, CallbackQuery: CallbackQuery, _):
    message_id = CallbackQuery.message.id
    task = lyrical.get(message_id)
    if not task:
        return await CallbackQuery.answer(
            "اكتمل التنزيل بالفعل.", show_alert=True
        )
    if task.done() or task.cancelled():
        return await CallbackQuery.answer(
            "اكتمل التنزيل أو تم إلغاؤه بالفعل.",
            show_alert=True,
        )
    if not task.done():
        try:
            task.cancel()
            try:
                lyrical.pop(message_id)
            except Exception:
                pass
            await CallbackQuery.answer("تم إلغاء التنزيل.", show_alert=True)
            return await CallbackQuery.edit_message_text(
                f"تم إلغاء التنزيل بواسطة {CallbackQuery.from_user.mention}"
            )
        except Exception:
            return await CallbackQuery.answer(
                "تعذر إلغاء التنزيل.", show_alert=True
            )
    await CallbackQuery.answer("تعذر العثور على مهمة التنزيل الحالية.", show_alert=True)
