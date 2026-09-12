from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery

import config
from AlexaMusic.logging import LOGGER
from AlexaMusic.utils.database import get_lang
from AlexaMusic.utils.rich_stream import send_control_panel_ephemeral
from strings import get_string


dispatcher = Dispatcher()


async def _language_for_chat(chat_id: int):
    try:
        return get_string(await get_lang(chat_id))
    except Exception:
        return get_string("ar")


@dispatcher.callback_query(F.data.startswith("RICHCTRL "))
async def open_rich_control_panel(callback: CallbackQuery) -> None:
    if not callback.data or not callback.from_user:
        return

    try:
        payload = callback.data.split(None, 1)[1]
        chat_value, requester_value = payload.split("|", 1)
        chat_id = int(chat_value)
        requester_id = int(requester_value)
    except Exception:
        await callback.answer("بيانات زر التحكم غير صالحة.", show_alert=True)
        return

    # Import lazily after the Pyrogram plugin set has already been loaded.
    from AlexaMusic.plugins.admins.callback import _can_use_rich_controls

    user_id = callback.from_user.id
    if not await _can_use_rich_controls(chat_id, user_id, requester_id):
        await callback.answer(
            "قائمة التحكم متاحة فقط لمطور البوت أو مالك القناة أو من بدأ التشغيل.",
            show_alert=True,
        )
        return

    try:
        await send_control_panel_ephemeral(
            chat_id,
            receiver_user_id=user_id,
            callback_query_id=str(callback.id),
            requester_id=requester_id,
        )
    except Exception:
        LOGGER(__name__).exception("Failed to open rich ephemeral control panel")
        await callback.answer(
            "تعذر فتح قائمة التحكم المؤقتة.",
            show_alert=True,
        )
        return

    try:
        await callback.answer()
    except Exception:
        pass


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
    """Receive Bot API callbacks that Pyrogram/Kurigram may not expose yet."""
    bot = Bot(token=config.BOT_TOKEN)
    try:
        # getUpdates cannot run while a Bot API webhook is configured.
        await bot.delete_webhook(drop_pending_updates=False)
        LOGGER(__name__).info(
            "Starting aiogram callback polling for rich/ephemeral controls."
        )
        await dispatcher.start_polling(
            bot,
            allowed_updates=["callback_query"],
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
