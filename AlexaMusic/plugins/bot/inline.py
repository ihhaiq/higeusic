# Copyright (C) 2025 by Alexa_Help @ Github, < https://github.com/TheTeamAlexa >
# Subscribe On YT < Jankari Ki Duniya >. All rights reserved. © Alexa © Yukki.

"""
TheTeamAlexa is a project of Telegram bots with variety of purposes.
Copyright (c) 2021 ~ Present Team Alexa <https://github.com/TheTeamAlexa>

This program is free software: you can redistribute it and can modify
as you want or you can collabe if you have new ideas.
"""

from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultPhoto,
)

from AlexaMusic import YouTube, app
from AlexaMusic.utils.inlinequery import answer
from config import BANNED_USERS, MUSIC_BOT_NAME


@app.on_inline_query(~BANNED_USERS)
async def inline_query_handler(client, query):
    text = query.query.strip().lower()
    if text.strip() == "":
        try:
            await client.answer_inline_query(query.id, results=answer, cache_time=10)
        except Exception:
            return
    else:
        try:
            result = await YouTube.search_many(text, limit=15)
        except Exception:
            return
        answers = []
        for item in result:
            title = (item.get("title") or "Unknown title").title()
            duration_seconds = int(item.get("duration") or 0)
            duration = (
                f"{duration_seconds // 60}:{duration_seconds % 60:02d}"
                if duration_seconds
                else "Live"
            )
            views = f"{int(item.get('view_count') or 0):,}"
            thumbnails = item.get("thumbnails") or []
            thumbnail = item.get("thumbnail") or (
                thumbnails[-1].get("url") if thumbnails else None
            )
            if not thumbnail:
                continue
            channellink = (
                item.get("channel_url")
                or item.get("uploader_url")
                or "https://youtube.com"
            )
            channel = item.get("channel") or item.get("uploader") or "Unknown"
            link = (
                item.get("webpage_url")
                or f"https://www.youtube.com/watch?v={item['id']}"
            )
            published = item.get("upload_date") or "Unknown"
            description = f"{views} | {duration} Mins | {channel}  | {published}"
            buttons = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="• ʏᴏᴜᴛᴜʙᴇ •",
                            url=link,
                        )
                    ],
                ]
            )
            searched_text = f"""
📌**ᴛɪᴛʟᴇ:** [{title}]({link})

⏳**ᴅᴜʀᴀᴛɪᴏɴ:** {duration} Mins
👀**ᴠɪᴇᴡs:** `{views}`
⏰**ᴩᴜʙʟɪsʜᴇᴅ ᴏɴ:** {published}
🎥**ᴄʜᴀɴɴᴇʟ:** {channel}
📎**ᴄʜᴀɴɴᴇʟ ʟɪɴᴋ:** [ᴠɪsɪᴛ ᴄʜᴀɴɴᴇʟ]({channellink})

💖 ** sᴇᴀʀᴄʜ ᴩᴏᴡᴇʀᴇᴅ ʙʏ {MUSIC_BOT_NAME} **"""
            answers.append(
                InlineQueryResultPhoto(
                    photo_url=thumbnail,
                    title=title,
                    thumb_url=thumbnail,
                    description=description,
                    caption=searched_text,
                    reply_markup=buttons,
                )
            )
        try:
            return await client.answer_inline_query(query.id, results=answers)
        except Exception:
            return
