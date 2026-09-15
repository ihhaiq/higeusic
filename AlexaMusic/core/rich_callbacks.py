from __future__ import annotations

import asyncio
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    KeyboardButtonRequestChat,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import config
from AlexaMusic.logging import LOGGER
from AlexaMusic.utils.database import get_lang
from AlexaMusic.utils.playback_cancel import cancel_play_operation
from AlexaMusic.utils.rich_stream import send_control_panel_ephemeral
from strings import get_string

dispatcher = Dispatcher()

CHAT_PICKER_REQUEST_ID = 20260916
_CHAT_PICKER_TEXTS = {"اضف مجموعة", "أضف مجموعة", "إضافة مجموعة"}


def _expired_callback(error: BaseException) -> bool:
    message = str(error).casefold()
    return "query is too old" in message or "query id is invalid" in message


async def _safe_answer(callback: CallbackQuery, text=None, *, show_alert=False):
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as error:
        if _expired_callback(error):
            LOGGER(__name__).warning(
                "Ignored expired rich callback query callback_id=%s",
                callback.id,
            )
            return False
        raise


async def _language_for_chat(chat_id: int):
    try:
        return get_string(await get_lang(chat_id))
    except Exception:
        return get_string("ar")


def _is_privileged_user(user_id: int | None) -> bool:
    if not user_id:
        return False

    from AlexaMusic.misc import SUDOERS

    return (
        user_id not in config.BANNED_USERS
        and (user_id == config.OWNER_ID or user_id in SUDOERS)
    )


def _private_controls_allowed(callback) -> bool:
    message = callback.message
    if not message or message.chat.id < 0:
        return True

    user_id = callback.from_user.id
    return message.chat.id == user_id and _is_privileged_user(user_id)


def _group_picker_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="➕ اختيار مجموعة",
                    request_chat=KeyboardButtonRequestChat(
                        request_id=CHAT_PICKER_REQUEST_ID,
                        chat_is_channel=False,
                        request_title=True,
                        request_username=True,
                    ),
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="اختر المجموعة الخاصة",
    )


@dispatcher.message(Command("addgroup"))
@dispatcher.message(F.text.in_(_CHAT_PICKER_TEXTS))
async def request_private_group(message: Message) -> None:
    if message.chat.type != ChatType.PRIVATE:
        return
    if not message.from_user or not _is_privileged_user(message.from_user.id):
        await message.answer(
            "إضافة وجهات البث من الخاص متاحة لمالك البوت والمطورين المخوّلين فقط."
        )
        return

    await message.answer(
        "اضغط «اختيار مجموعة» ثم اختر المجموعة الخاصة التي يوجد فيها الحساب المساعد.",
        reply_markup=_group_picker_keyboard(),
    )


@dispatcher.message(F.chat_shared)
async def receive_private_group_selection(message: Message) -> None:
    if (
        message.chat.type != ChatType.PRIVATE
        or not message.from_user
        or not message.chat_shared
        or message.chat_shared.request_id != CHAT_PICKER_REQUEST_ID
    ):
        return

    if not _is_privileged_user(message.from_user.id):
        await message.answer(
            "إضافة وجهات البث من الخاص متاحة لمالك البوت والمطورين المخوّلين فقط.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    chat_id = int(message.chat_shared.chat_id)

    try:
        from AlexaMusic.utils.private_play import (
            prepare_private_assistant,
            resolve_private_chat,
        )

        chat = await resolve_private_chat(chat_id)
        await prepare_private_assistant(chat)
    except Exception as error:
        LOGGER(__name__).warning(
            "Shared private group could not be resolved by assistant chat_id=%s: %s",
            chat_id,
            error,
        )
        await message.answer(
            "تم استلام معرّف المجموعة، لكن الحساب المساعد لم يستطع الوصول إليها.\n\n"
            f"ID: <code>{chat_id}</code>\n"
            f"السبب: {escape(str(error).strip() or type(error).__name__)}",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    from AlexaMusic.utils.database import add_private_chat, is_served_private_chat

    already_authorized = await is_served_private_chat(chat_id)
    if not already_authorized:
        await add_private_chat(chat_id)

    title = chat.title or message.chat_shared.title or "المجموعة المختارة"
    authorization_line = (
        "كانت المجموعة مصرّحة مسبقًا."
        if already_authorized
        else "تمت إضافة المجموعة تلقائيًا إلى وجهات البث المصرّحة."
    )

    await message.answer(
        "✅ تم اختيار المجموعة بنجاح.\n\n"
        f"الاسم: <b>{escape(title)}</b>\n"
        f"ID: <code>{chat_id}</code>\n"
        f"{authorization_line}\n"
        "الحساب المساعد: ✅ موجود ويمكنه الوصول للمجموعة\n\n"
        "تقدر الآن تستخدم المعرف مباشرة، مثل:\n"
        f"<code>/play {chat_id} اسم الأغنية</code>\n"
        f"<code>فيديو {chat_id} رابط_الفيديو</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )


@dispatcher.callback_query(F.data.startswith("PLAYCANCEL "))
async def cancel_play_preparation(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return
    try:
        token = callback.data.split(None, 1)[1].strip()
    except Exception:
        await _safe_answer(callback, "بيانات الإلغاء غير صالحة.", show_alert=True)
        return

    from AlexaMusic.misc import SUDOERS

    user_id = int(callback.from_user.id)
    privileged = (
        {user_id}
        if user_id == int(config.OWNER_ID) or user_id in SUDOERS
        else set()
    )
    result = cancel_play_operation(
        token,
        user_id=user_id,
        privileged_user_ids=privileged,
    )
    if result == "forbidden":
        await _safe_answer(
            callback,
            "هذا الطلب يخص مستخدمًا آخر.",
            show_alert=True,
        )
        return
    if result == "missing":
        await _safe_answer(
            callback,
            "انتهت العملية أو تم إلغاؤها مسبقًا.",
            show_alert=True,
        )
        return

    await _safe_answer(callback, "تم إلغاء العملية.")
    if callback.message:
        try:
            await callback.message.edit_text("✖️ تم إلغاء العملية.")
        except Exception:
            pass


@dispatcher.callback_query(F.data.startswith("RICHCTRL "))
async def open_rich_control_panel(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user or not callback.message:
        return
    if not _private_controls_allowed(callback):
        await _safe_answer(callback, "التحكم من الخاص متاح لمالك البوت والمطورين المخوّلين فقط.", show_alert=True)
        return

    try:
        payload = callback.data.split(None, 1)[1]
        chat_value, requester_value = payload.split("|", 1)
        chat_id = int(chat_value)
        requester_id = int(requester_value)
    except Exception:
        await _safe_answer(
            callback,
            "بيانات زر التحكم غير صالحة.",
            show_alert=True,
        )
        return

    # Import lazily after the Pyrogram plugin set has already been loaded.
    from AlexaMusic.plugins.admins.callback import _can_use_rich_controls

    user_id = callback.from_user.id
    if not await _can_use_rich_controls(chat_id, user_id, requester_id):
        await _safe_answer(
            callback,
            "قائمة التحكم متاحة فقط لمطور البوت أو مالك القناة أو من بدأ التشغيل.",
            show_alert=True,
        )
        return

    from AlexaMusic.utils.database import is_active_chat

    if not await is_active_chat(chat_id):
        await _safe_answer(callback, "لا يوجد تشغيل فعّال لهذه المجموعة/القناة.", show_alert=True)
        return

    delivery_chat_id = callback.message.chat.id
    if delivery_chat_id > 0:
        await _safe_answer(callback)
    try:
        await send_control_panel_ephemeral(
            chat_id,
            receiver_user_id=user_id,
            callback_query_id=str(callback.id),
            requester_id=requester_id,
            delivery_chat_id=delivery_chat_id,
        )
    except TelegramBadRequest as error:
        if _expired_callback(error):
            LOGGER(__name__).warning(
                "Rich control callback expired before the ephemeral panel opened "
                "callback_id=%s",
                callback.id,
            )
        else:
            LOGGER(__name__).exception("Failed to open rich ephemeral control panel")
            await _safe_answer(
                callback,
                "تعذر فتح قائمة التحكم المؤقتة.",
                show_alert=True,
            )
        return
    except Exception:
        LOGGER(__name__).exception("Failed to open rich ephemeral control panel")
        await _safe_answer(
            callback,
            "تعذر فتح قائمة التحكم المؤقتة.",
            show_alert=True,
        )
        return

    # Sending the ephemeral message with callback_query_id consumes the query;
    # answering it again would itself produce "query ID is invalid".


class _AiogramCallbackAdapter:
    """Minimal adapter for the existing framework-neutral rich control logic."""

    def __init__(self, callback: CallbackQuery) -> None:
        self._callback = callback
        self.from_user = callback.from_user

    async def answer(self, text=None, show_alert: bool = False):
        return await self._callback.answer(text=text, show_alert=show_alert)


@dispatcher.callback_query(F.data.startswith("RCTRL "))
async def handle_rich_control_action(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return
    if not _private_controls_allowed(callback):
        await _safe_answer(callback, "غير مسموح لك بالتحكم بهذا التشغيل.", show_alert=True)
        return

    try:
        payload = callback.data.split(None, 1)[1]
        command, chat_value, requester_value = payload.split("|", 2)
        chat_id = int(chat_value)
        requester_id = int(requester_value)
    except Exception:
        await callback.answer("بيانات التحكم غير صالحة.", show_alert=True)
        return

    from AlexaMusic.plugins.admins.callback import (
        _can_use_rich_controls,
        _handle_rich_control_action,
    )
    from AlexaMusic.utils.database import is_active_chat

    if not await is_active_chat(chat_id):
        language = await _language_for_chat(chat_id)
        await callback.answer(language["general_6"], show_alert=True)
        return

    if not await _can_use_rich_controls(
        chat_id,
        callback.from_user.id,
        requester_id,
    ):
        await callback.answer(
            "غير مسموح لك بالتحكم بهذا التشغيل.",
            show_alert=True,
        )
        return

    language = await _language_for_chat(chat_id)
    adapter = _AiogramCallbackAdapter(callback)

    try:
        await _handle_rich_control_action(
            adapter,
            language,
            command,
            chat_id,
        )
    except Exception:
        LOGGER(__name__).exception(
            "Rich control action failed: command=%s chat_id=%s",
            command,
            chat_id,
        )
        try:
            await callback.answer(
                "تعذر تنفيذ أمر التحكم.",
                show_alert=True,
            )
        except Exception:
            pass


async def run_rich_callback_polling() -> None:
    """Receive Bot API callbacks and service messages not exposed by Pyrogram/Kurigram."""

    bot = Bot(token=config.BOT_TOKEN)
    try:
        # getUpdates cannot run while a Bot API webhook is configured.
        # Old callback IDs cannot open ephemeral messages and otherwise create
        # a traceback loop after a Railway restart.
        await bot.delete_webhook(drop_pending_updates=True)
        LOGGER(__name__).info(
            "Starting aiogram polling for rich controls and private chat selection."
        )
        await dispatcher.start_polling(
            bot,
            allowed_updates=["callback_query", "message"],
            handle_signals=False,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        LOGGER(__name__).exception("Rich callback polling stopped unexpectedly.")
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
