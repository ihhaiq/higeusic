# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio

from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from AlexaMusic import YouTube, app
from AlexaMusic.logging import LOGGER
from AlexaMusic.misc import SUDOERS
from AlexaMusic.utils.database import (
    get_assistant,
    get_cmode,
    get_lang,
    get_playmode,
    get_playtype,
    is_active_chat,
    is_commanddelete_on,
    is_served_private_chat,
)
from AlexaMusic.utils.database.memorydatabase import is_maintenance
from AlexaMusic.utils.exceptions import AssistantErr
from AlexaMusic.utils.inline.playlist import botplaylist_markup
from AlexaMusic.utils.play_request import is_video_request, play_command_name
from config import OWNER_ID, PLAYLIST_IMG_URL, PRIVATE_BOT_MODE, adminlist
from strings import get_string

links = {}


def PlayWrapper(command):
    async def wrapper(client, message):
        is_channel_post = message.chat.type == ChatType.CHANNEL
        actor_id = message.from_user.id if message.from_user else OWNER_ID

        if await is_maintenance() is False and actor_id not in SUDOERS:
            return await message.reply_text(
                "البوت في وضع الصيانة حالياً. يرجى المحاولة لاحقاً."
            )
        if PRIVATE_BOT_MODE == str(True) and not await is_served_private_chat(
            message.chat.id
        ):
            await message.reply_text(
                "**بوت موسيقى خاص**\n\nهذه المحادثة غير مخولة لاستخدام البوت. اطلب من المالك تخويلها أولاً."
            )
            return await app.leave_chat(message.chat.id)
        if not is_channel_post and await is_commanddelete_on(message.chat.id):
            try:
                await message.delete()
            except Exception:
                pass
        language = await get_lang(message.chat.id)
        _ = get_string(language)
        audio_telegram = (
            (message.reply_to_message.audio or message.reply_to_message.voice)
            if message.reply_to_message
            else None
        )
        video_telegram = (
            (message.reply_to_message.video or message.reply_to_message.document)
            if message.reply_to_message
            else None
        )
        url = await YouTube.url(message)
        if (
            audio_telegram is None
            and video_telegram is None
            and url is None
            and len(message.command) < 2
        ):
            if "stream" in message.command:
                return await message.reply_text(_["str_1"])
            buttons = botplaylist_markup(_)
            return await message.reply_photo(
                photo=PLAYLIST_IMG_URL,
                caption=_["playlist_1"],
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        if message.sender_chat and not is_channel_post:
            upl = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="طريقة الحل",
                            callback_data="AnonymousAdmin",
                        ),
                    ]
                ]
            )
            return await message.reply_text(_["general_4"], reply_markup=upl)
        if is_channel_post:
            # A /play post in a channel targets that channel's own voice chat.
            chat_id = message.chat.id
            channel = None
        elif message.command[0][0] == "c":
            chat_id = await get_cmode(message.chat.id)
            if chat_id is None:
                return await message.reply_text(_["setting_12"])
            try:
                chat = await app.get_chat(chat_id)
            except Exception:
                return await message.reply_text(_["cplay_4"])
            channel = chat.title
        else:
            chat_id = message.chat.id
            channel = None
        playmode = await get_playmode(message.chat.id)
        playty = await get_playtype(message.chat.id)
        # Only channel admins can publish channel posts, and Telegram doesn't
        # expose the posting admin as from_user to bots.
        if not is_channel_post and playty != "Everyone" and actor_id not in SUDOERS:
            admins = adminlist.get(message.chat.id)
            if not admins:
                return await message.reply_text(_["admin_18"])
            if actor_id not in admins:
                return await message.reply_text(_["play_4"])
        command_name = play_command_name(message)
        video = True if is_video_request(message) else None
        LOGGER(__name__).info(
            "Play request parsed chat_id=%s command=%s mode=%s playmode=%s",
            chat_id,
            command_name,
            "video" if video else "audio",
            playmode,
        )
        if command_name.endswith("force"):
            if not await is_active_chat(chat_id):
                return await message.reply_text(_["play_18"])
            fplay = True
        else:
            fplay = None

        if not await is_active_chat(chat_id):
            try:
                userbot = await get_assistant(chat_id)
            except AssistantErr as error:
                return await message.reply_text(str(error))
            try:
                try:
                    get = await app.get_chat_member(chat_id, userbot.id)
                except ChatAdminRequired:
                    return await message.reply_text(_["call_12"])
                if get.status in [
                    ChatMemberStatus.BANNED,
                    ChatMemberStatus.RESTRICTED,
                ]:
                    return await message.reply_text(
                        _["call_13"].format(
                            app.mention, userbot.id, userbot.name, userbot.username
                        )
                    )
            except UserNotParticipant:
                if chat_id in links:
                    invitelink = links[chat_id]
                else:
                    if message.chat.username:
                        invitelink = message.chat.username
                        try:
                            await userbot.resolve_peer(invitelink)
                        except Exception:
                            pass
                    else:
                        try:
                            invitelink = await app.export_chat_invite_link(chat_id)
                        except ChatAdminRequired:
                            return await message.reply_text(_["call_12"])
                        except Exception as e:
                            return await message.reply_text(
                                _["call_14"].format(app.mention, type(e).__name__)
                            )

                if invitelink.startswith("https://t.me/+"):
                    invitelink = invitelink.replace(
                        "https://t.me/+", "https://t.me/joinchat/"
                    )
                myu = await message.reply_text(_["call_15"].format(app.mention))
                try:
                    await asyncio.sleep(1)
                    await userbot.join_chat(invitelink)
                except InviteRequestSent:
                    try:
                        await app.approve_chat_join_request(chat_id, userbot.id)
                    except Exception as e:
                        return await message.reply_text(
                            _["call_14"].format(app.mention, type(e).__name__)
                        )
                    await asyncio.sleep(3)
                    await myu.edit(_["call_16"].format(app.mention))
                except UserAlreadyParticipant:
                    pass
                except Exception as e:
                    return await message.reply_text(
                        _["call_14"].format(app.mention, type(e).__name__)
                    )

                links[chat_id] = invitelink

                try:
                    await userbot.resolve_peer(chat_id)
                except Exception:
                    pass

        return await command(
            client,
            message,
            _,
            chat_id,
            video,
            channel,
            playmode,
            url,
            fplay,
        )

    return wrapper
