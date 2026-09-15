"""Select private playback groups from the bot DM using Kurigram request_chat."""

from html import escape

from pyrogram import enums, filters
from pyrogram.types import (
    KeyboardButton,
    KeyboardButtonRequestChat,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import config
from AlexaMusic import app
from AlexaMusic.logging import LOGGER
from AlexaMusic.misc import SUDOERS
from AlexaMusic.utils.database import add_private_chat, is_served_private_chat
from AlexaMusic.utils.private_play import prepare_private_assistant, resolve_private_chat

GROUP_PICKER_BUTTON_ID = 20260916
_GROUP_PICKER_TEXT = r"^(?:اضف مجموعة|أضف مجموعة|إضافة مجموعة)$"


def _allowed(user_id: int | None) -> bool:
    return bool(user_id) and (
        user_id == config.OWNER_ID or user_id in SUDOERS
    )


def _picker_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "➕ اختيار مجموعة",
                    request_chat=KeyboardButtonRequestChat(
                        button_id=GROUP_PICKER_BUTTON_ID,
                        chat_is_channel=False,
                        request_title=True,
                        request_username=True,
                    ),
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        placeholder="اختر المجموعة الخاصة",
    )


@app.on_message(
    (
        filters.command("addgroup")
        | filters.regex(_GROUP_PICKER_TEXT)
    )
    & filters.private
    & ~config.BANNED_USERS
)
async def request_private_group(client, message):
    user_id = message.from_user.id if message.from_user else None
    if not _allowed(user_id):
        return await message.reply_text(
            "إضافة وجهات البث من الخاص متاحة لمالك البوت والمطورين المخوّلين فقط."
        )

    await message.reply_text(
        "اضغط «اختيار مجموعة» ثم اختر المجموعة الخاصة التي يوجد فيها الحساب المساعد.",
        reply_markup=_picker_keyboard(),
    )


@app.on_message(filters.chat_shared & filters.private & ~config.BANNED_USERS)
async def receive_private_group_selection(client, message):
    shared = message.chat_shared
    user_id = message.from_user.id if message.from_user else None

    if not shared or shared.button_id != GROUP_PICKER_BUTTON_ID:
        return
    if not _allowed(user_id):
        return await message.reply_text(
            "إضافة وجهات البث من الخاص متاحة لمالك البوت والمطورين المخوّلين فقط.",
            reply_markup=ReplyKeyboardRemove(),
        )

    chat_id = int(shared.chat.id)

    try:
        chat = await resolve_private_chat(chat_id)
        await prepare_private_assistant(chat)
    except Exception as error:
        LOGGER(__name__).warning(
            "Shared private group could not be resolved by assistant chat_id=%s: %s",
            chat_id,
            error,
        )
        return await message.reply_text(
            "تم استلام معرّف المجموعة، لكن الحساب المساعد لم يستطع الوصول إليها.\n\n"
            f"ID: <code>{chat_id}</code>\n"
            f"السبب: {escape(str(error).strip() or type(error).__name__)}",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )

    already_authorized = await is_served_private_chat(chat_id)
    if not already_authorized:
        await add_private_chat(chat_id)

    title = chat.title or shared.chat.title or "المجموعة المختارة"
    authorization_line = (
        "كانت المجموعة مصرّحة مسبقًا."
        if already_authorized
        else "تمت إضافة المجموعة تلقائيًا إلى وجهات البث المصرّحة."
    )

    await message.reply_text(
        "✅ تم اختيار المجموعة بنجاح.\n\n"
        f"الاسم: <b>{escape(title)}</b>\n"
        f"ID: <code>{chat_id}</code>\n"
        f"{authorization_line}\n"
        "الحساب المساعد: ✅ موجود ويمكنه الوصول للمجموعة\n\n"
        "تقدر الآن تستخدم المعرف مباشرة، مثل:\n"
        f"<code>/play {chat_id} اسم الأغنية</code>\n"
        f"<code>فيديو {chat_id} رابط_الفيديو</code>",
        parse_mode=enums.ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
