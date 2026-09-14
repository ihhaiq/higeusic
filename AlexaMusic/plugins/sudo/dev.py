"""Owner panel for the playback destination allowlist."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
from AlexaMusic import app
from AlexaMusic.misc import SUDOERS
from AlexaMusic.utils.database import (
    add_private_chat,
    get_private_served_chats,
    is_served_private_chat,
    remove_private_chat,
)
from AlexaMusic.utils.private_play import resolve_private_chat


_pending_actions: dict[int, str] = {}


def _is_developer(user_id: int | None) -> bool:
    return bool(user_id) and (user_id == config.OWNER_ID or user_id in SUDOERS)


def _panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ إضافة قناة", callback_data="dev:add"),
                InlineKeyboardButton("➖ حذف قناة", callback_data="dev:remove"),
            ],
            [InlineKeyboardButton("📋 القنوات المصرحة", callback_data="dev:list")],
            [InlineKeyboardButton("✖️ إغلاق", callback_data="dev:close")],
        ]
    )


def _back_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("رجوع", callback_data="dev:home")]]
    )


async def _authorized_list() -> str:
    rows = await get_private_served_chats()
    chat_ids = sorted(int(row["chat_id"]) for row in rows)
    if not chat_ids:
        return "لا توجد قنوات أو مجموعات مصرحة حالياً."

    lines = ["القنوات والمجموعات المصرحة:"]
    for index, chat_id in enumerate(chat_ids, start=1):
        try:
            chat = await resolve_private_chat(str(chat_id))
            title = chat.title or str(chat_id)
        except Exception:
            title = "غير متاحة للحساب المساعد"
        lines.append(f"{index}. {title} (`{chat_id}`)")
    return "\n".join(lines)


async def _change_authorization(message, action: str, target: str) -> None:
    try:
        chat = await resolve_private_chat(target)
    except Exception as error:
        await message.reply_text(
            "تعذر العثور على المجموعة/القناة. أرسل @المعرف أو الآيدي السالب، "
            "وتأكد أن الحساب المساعد عضو فيها. "
            f"({type(error).__name__})"
        )
        return

    authorized = await is_served_private_chat(chat.id)
    if action == "add":
        if authorized:
            await message.reply_text(f"{chat.title} مصرحة مسبقاً (`{chat.id}`).")
            return
        await add_private_chat(chat.id)
        await message.reply_text(
            f"تمت إضافة {chat.title} إلى القنوات المصرحة (`{chat.id}`)."
        )
        return

    if not authorized:
        await message.reply_text(f"{chat.title} غير موجودة في قائمة التصريح.")
        return
    await remove_private_chat(chat.id)
    await message.reply_text(f"تم حذف تصريح {chat.title} (`{chat.id}`).")


@app.on_message(filters.command("dev") & filters.private)
async def developer_panel(client, message):
    if not _is_developer(message.from_user.id if message.from_user else None):
        return await message.reply_text("هذه اللوحة متاحة لمالك البوت والمطورين فقط.")

    args = message.text.split(maxsplit=2)
    if len(args) >= 2:
        action = args[1].strip().lower()
        aliases = {
            "add": "add",
            "اضف": "add",
            "أضف": "add",
            "remove": "remove",
            "delete": "remove",
            "حذف": "remove",
        }
        if action in {"list", "قائمة"}:
            return await message.reply_text(await _authorized_list())
        if action in aliases and len(args) == 3:
            return await _change_authorization(message, aliases[action], args[2].strip())

    await message.reply_text(
        "لوحة المطور — السماح بالتشغيل للقنوات والمجموعات المصرحة فقط.",
        reply_markup=_panel(),
    )


@app.on_callback_query(filters.regex(r"^dev:"))
async def developer_panel_callback(client, callback):
    user_id = callback.from_user.id if callback.from_user else None
    if not _is_developer(user_id):
        return await callback.answer("غير مسموح.", show_alert=True)

    action = callback.data.split(":", 1)[1]
    if action == "close":
        _pending_actions.pop(user_id, None)
        await callback.message.delete()
        return await callback.answer()
    if action == "home":
        _pending_actions.pop(user_id, None)
        await callback.message.edit_text(
            "لوحة المطور — السماح بالتشغيل للقنوات والمجموعات المصرحة فقط.",
            reply_markup=_panel(),
        )
        return await callback.answer()
    if action == "list":
        await callback.message.edit_text(
            await _authorized_list(),
            reply_markup=_back_button(),
        )
        return await callback.answer()
    if action in {"add", "remove"}:
        _pending_actions[user_id] = action
        verb = "إضافتها" if action == "add" else "حذف تصريحها"
        await callback.message.edit_text(
            f"أرسل الآن @معرف القناة/المجموعة أو الآيدي السالب حتى يتم {verb}.",
            reply_markup=_back_button(),
        )
        return await callback.answer()
    await callback.answer("خيار غير معروف.", show_alert=True)


@app.on_message(filters.private & filters.text, group=-1)
async def developer_panel_target(client, message):
    user_id = message.from_user.id if message.from_user else None
    action = _pending_actions.get(user_id)
    if not action or not _is_developer(user_id):
        return
    if message.text.startswith("/"):
        return
    _pending_actions.pop(user_id, None)
    await _change_authorization(message, action, message.text.strip())
