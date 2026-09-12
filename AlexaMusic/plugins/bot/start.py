# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

import asyncio

from pyrogram import enums, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from AlexaMusic import Telegram, YouTube, app
from AlexaMusic.misc import SUDOERS
from AlexaMusic.plugins.play.playlist import del_plist_msg
from AlexaMusic.plugins.sudo.sudoers import sudoers_list
from AlexaMusic.utils.command import commandpro
from AlexaMusic.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_assistant,
    get_lang,
    get_userss,
    is_on_off,
    is_served_private_chat,
    is_served_user,
)
from AlexaMusic.utils.decorators.language import LanguageStart
from AlexaMusic.utils.inline import help_pannel, private_panel, start_pannel
from config import BANNED_USERS
from config.config import OWNER_ID
from strings import get_command, get_string

loop = asyncio.get_running_loop()


@app.on_message(
    filters.command(get_command("START_COMMAND")) & filters.private & ~BANNED_USERS
)
@LanguageStart
async def start_comm(client, message: Message, _):
    await add_served_user(message.from_user.id)
    if len(message.text.split()) > 1:
        name = message.text.split(None, 1)[1]
        if name[:4] == "help":
            keyboard = help_pannel(_)
            return await message.reply_text(_["help_1"], reply_markup=keyboard)
        if name[:4] == "song":
            return await message.reply_text(_["song_2"])
        if name[:3] == "sta":
            m = await message.reply_text(
                f"⏳ جاري جلب إحصائياتك الشخصية من {config.MUSIC_BOT_NAME}..."
            )
            stats = await get_userss(message.from_user.id)
            tot = len(stats)
            if not stats:
                await asyncio.sleep(1)
                return await m.edit(_["ustats_1"])

            def get_stats():
                msg = ""
                limit = 0
                results = {}
                for i in stats:
                    top_list = stats[i]["spot"]
                    results[str(i)] = top_list
                    list_arranged = dict(
                        sorted(
                            results.items(),
                            key=lambda item: item[1],
                            reverse=True,
                        )
                    )
                if not results:
                    return m.edit(_["ustats_1"])
                tota = 0
                videoid = None
                for vidid, count in list_arranged.items():
                    tota += count
                    if limit == 10:
                        continue
                    if limit == 0:
                        videoid = vidid
                    limit += 1
                    details = stats.get(vidid)
                    title = (details["title"][:35]).title()
                    if vidid == "telegram":
                        msg += f"🔗 **وسائط تيليجرام** — تم تشغيلها {count} مرة\n\n"
                    else:
                        msg += f"🔗 [{title}](https://www.youtube.com/watch?v={vidid}) — تم تشغيله {count} مرة\n\n"
                msg = _["ustats_2"].format(tot, tota, limit) + msg
                return videoid, msg

            try:
                videoid, msg = await loop.run_in_executor(None, get_stats)
            except Exception as e:
                print(e)
                return
            thumbnail = await YouTube.thumbnail(videoid, True)
            await m.delete()
            await message.reply_photo(photo=thumbnail, caption=msg)
            return
        if name[:3] == "sud":
            await sudoers_list(client=client, message=message, _=_)
            if await is_on_off(config.LOG):
                sender_id = message.from_user.id
                sender_name = message.from_user.first_name
                return await app.send_message(
                    config.LOG_GROUP_ID,
                    f"{message.from_user.mention} فتح قائمة <code>sudolist</code>\n\n**معرّف المستخدم:** {sender_id}\n**الاسم:** {sender_name}",
                )
            return
        if name[:3] == "lyr":
            query = (str(name)).replace("lyrics_", "", 1)
            lyrical = config.lyrical
            lyrics = lyrical.get(query)
            if lyrics:
                return await Telegram.send_split_text(message, lyrics)
            else:
                return await message.reply_text("تعذر جلب كلمات الأغنية.")
        if name[0:3] == "del":
            await del_plist_msg(client=client, message=message, _=_)
        if name[0:3] == "inf":
            m = await message.reply_text("🔎")
            query = (str(name)).replace("info_", "", 1)
            query = f"https://www.youtube.com/watch?v={query}"
            try:
                result = await YouTube.info(query)
            except Exception as error:
                await m.delete()
                return await message.reply_text(YouTube.friendly_error(error))
            title = result.get("title") or "Unknown title"
            duration_seconds = int(result.get("duration") or 0)
            duration = (
                f"{duration_seconds // 60}:{duration_seconds % 60:02d}"
                if duration_seconds
                else "بث مباشر"
            )
            views = f"{int(result.get('view_count') or 0):,}"
            thumbnail = result.get("thumbnail") or config.YOUTUBE_IMG_URL
            channellink = (
                result.get("channel_url") or result.get("uploader_url") or query
            )
            channel = result.get("channel") or result.get("uploader") or "غير معروف"
            link = result.get("webpage_url") or query
            published = result.get("upload_date") or "غير معروف"
            searched_text = f"""
🎵 **معلومات المقطع**

📌 **العنوان:** {title}
⏳ **المدة:** {duration}
👀 **المشاهدات:** `{views}`
⏰ **تاريخ النشر:** {published}
🎥 **القناة:** {channel}
📎 **رابط القناة:** [فتح القناة]({channellink})
🔗 **الرابط:** [المشاهدة على يوتيوب]({link})

🔎 البحث بواسطة {config.MUSIC_BOT_NAME}"""
            key = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(text="يوتيوب", url=f"{link}"),
                        InlineKeyboardButton(text="إغلاق", callback_data="close"),
                    ],
                ]
            )
            await m.delete()
            await app.send_photo(
                message.chat.id,
                photo=thumbnail,
                caption=searched_text,
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=key,
            )
            if await is_on_off(config.LOG):
                sender_id = message.from_user.id
                sender_name = message.from_user.first_name
                return await app.send_message(
                    config.LOG_GROUP_ID,
                    f"{message.from_user.mention} طلب معلومات مقطع\n\n**معرّف المستخدم:** {sender_id}\n**الاسم:** {sender_name}",
                )
    else:
        try:
            await app.resolve_peer(OWNER_ID)
            OWNER = OWNER_ID
        except Exception:
            OWNER = None
        out = private_panel(_, app.username, OWNER)
        if config.START_IMG_URL:
            try:
                await message.reply_photo(
                    photo=config.START_IMG_URL,
                    caption=_["start_2"].format(message.from_user.mention, app.mention),
                    reply_markup=InlineKeyboardMarkup(out),
                )
            except Exception:
                await message.reply_text(
                    text=_["start_2"].format(message.from_user.mention, app.mention),
                    reply_markup=InlineKeyboardMarkup(out),
                )
        else:
            await message.reply_text(
                text=_["start_2"].format(message.from_user.mention, app.mention),
                reply_markup=InlineKeyboardMarkup(out),
            )
        if await is_on_off(config.LOG):
            sender_id = message.from_user.id
            sender_name = message.from_user.first_name
            return await app.send_message(
                config.LOG_GROUP_ID,
                f"{message.from_user.mention} بدأ استخدام البوت.\n\n**معرّف المستخدم:** {sender_id}\n**الاسم:** {sender_name}",
            )


@app.on_message(
    filters.command(get_command("START_COMMAND")) & filters.group & ~BANNED_USERS
)
@LanguageStart
async def testbot(client, message: Message, _):
    out = start_pannel(_)
    return await message.reply_text(
        _["start_1"].format(message.chat.title, config.MUSIC_BOT_NAME),
        reply_markup=InlineKeyboardMarkup(out),
    )


welcome_group = 2


@app.on_message(filters.new_chat_members, group=welcome_group)
async def welcome(client, message: Message):
    chat_id = message.chat.id
    if config.PRIVATE_BOT_MODE == str(True):
        if not await is_served_private_chat(message.chat.id):
            await message.reply_text(
                "**بوت موسيقى خاص**\n\nهذه المحادثة غير مخولة لاستخدام البوت. اطلب من مالك البوت تخويلها أولاً."
            )
            return await app.leave_chat(message.chat.id)
    else:
        await add_served_chat(chat_id)
    for member in message.new_chat_members:
        try:
            language = await get_lang(message.chat.id)
            _ = get_string(language)
            if member.id == app.id:
                chat_type = message.chat.type
                if chat_type != enums.ChatType.SUPERGROUP:
                    await message.reply_text(_["start_6"])
                    return await app.leave_chat(message.chat.id)
                if chat_id in await blacklisted_chats():
                    await message.reply_text(
                        _["start_7"].format(
                            f"https://t.me/{app.username}?start=sudolist"
                        )
                    )
                    return await app.leave_chat(chat_id)
                userbot = await get_assistant(message.chat.id)
                out = start_pannel(_)
                await message.reply_text(
                    _["start_3"].format(
                        config.MUSIC_BOT_NAME,
                        userbot.username,
                        userbot.id,
                    ),
                    reply_markup=InlineKeyboardMarkup(out),
                )
            if member.id == config.OWNER_ID:
                return await message.reply_text(
                    _["start_4"].format(config.MUSIC_BOT_NAME, member.mention)
                )
            if member.id in SUDOERS:
                return await message.reply_text(
                    _["start_5"].format(config.MUSIC_BOT_NAME, member.mention)
                )
            return
        except Exception:
            return


@app.on_message(commandpro(["/alive", "Alexa"]))
async def alive(client, message: Message):
    await message.reply_photo(
        photo=config.PING_IMG_URL,
        caption=f"""✅ **البوت يعمل بصورة طبيعية**

🤖 **الاسم:** {config.MUSIC_BOT_NAME}
📦 **المستودع:** {config.GITHUB_REPO}

استخدم /help لعرض الأوامر.""",
    )


@app.on_message(commandpro(["/verify", "alexaverification"]))
async def verify(client, message: Message):
    if await is_served_user(message.from_user.id):
        await message.reply_text(
            text="✅ أنت مسجل مسبقاً في قاعدة مستخدمي البوت.",
        )
        return
    await add_served_user(message.from_user.id)
    await message.reply_photo(
        photo="https://telegra.ph/file/7f08acd78577f99f60ff5.png",
        caption="✅ تم تسجيلك بنجاح في قاعدة مستخدمي البوت.",
    )
