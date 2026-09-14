"""Owner/sudo video playback from the bot's private chat."""

import asyncio
from collections import defaultdict

from pyrogram import filters
from pyrogram.errors import FloodWait

import config
from AlexaMusic import YouTube, app
from AlexaMusic.core.call import Alexa
from AlexaMusic.logging import LOGGER
from AlexaMusic.misc import SUDOERS
from AlexaMusic.utils.database import (
    blacklisted_chats,
    get_lang,
    is_served_private_chat,
)
from AlexaMusic.utils.exceptions import AssistantErr
from AlexaMusic.utils.play_request import parse_private_video_request
from AlexaMusic.utils.private_play import prepare_private_assistant, resolve_private_chat
from strings import get_string

from .play import play_media

_play_locks = defaultdict(asyncio.Lock)
USAGE = (
    "للتشغيل من الخاص:\n"
    "فيديو @المجموعة رابط_الفيديو أو اسم_الفيديو\n\n"
    "أو أرسل ملف فيديو ورد عليه بـ: فيديو @المجموعة\n"
    "يمكن استخدام آيدي المجموعة/القناة السالب بدل اليوزر.\n"
    "الحساب المساعد يجب أن يكون عضواً ومسموحاً له بالبث، والمكالمة مفتوحة."
)


@app.on_message(
    (filters.command(["vplay", "فيديو"]) | filters.command(["فيديو"], prefixes=""))
    & filters.private
    & ~config.BANNED_USERS
)
async def private_video(client, message):
    if not message.from_user or (
        message.from_user.id != config.OWNER_ID and message.from_user.id not in SUDOERS
    ):
        return await message.reply_text("التشغيل من الخاص متاح لمالك البوت والمطورين المخوّلين فقط.")
    try:
        request = parse_private_video_request(message)
    except ValueError:
        return await message.reply_text(USAGE)

    reply = message.reply_to_message
    has_media = reply and (reply.video or reply.document or reply.audio or reply.voice)
    url = await YouTube.url(message)
    if not request.query and not has_media and not url:
        return await message.reply_text(USAGE)

    try:
        chat = await resolve_private_chat(request.target)
        if chat.id in await blacklisted_chats():
            return await message.reply_text("هذه المجموعة/القناة محظورة من استخدام البوت.")
        if config.PRIVATE_BOT_MODE == str(True) and not await is_served_private_chat(chat.id):
            return await message.reply_text("خوّل المجموعة/القناة في وضع البوت الخاص أولاً.")
        async with _play_locks[chat.id]:
            number = await prepare_private_assistant(chat)
            # The call engine has its own Pyrogram client and peer cache.
            await getattr(Alexa, f"userbot{number}").get_chat(chat.username or chat.id)
            language = get_string(await get_lang(message.chat.id))
            await play_media(
                client, message, language, chat.id, True, chat.title,
                "Direct", url, None, query=request.query,
            )
    except AssistantErr as error:
        await message.reply_text(str(error))
    except FloodWait as error:
        await message.reply_text(f"تيليجرام طلب الانتظار {error.value} ثانية. حاول بعدها.")
    except Exception as error:
        LOGGER(__name__).exception("Private video playback failed")
        await message.reply_text(f"تعذر بدء التشغيل من الخاص ({type(error).__name__}).")
