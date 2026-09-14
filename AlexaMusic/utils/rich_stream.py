from __future__ import annotations

import os
from typing import Any

from aiogram import Bot
from aiogram.types import EphemeralMessageParameters, FSInputFile, InputMediaPhoto, InputRichMessage

import config


def _button(text: str, *, callback_data: str | None = None, url: str | None = None, style: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {"text": text}
    if callback_data:
        button["callback_data"] = callback_data
    if url:
        button["url"] = url
    if style in {"primary", "success", "danger"}:
        button["style"] = style
    return {"type": "button", "button": button}


def _media(image: str):
    return FSInputFile(image) if os.path.isfile(image) else image


async def send_stream_rich_message(
    chat_id: int,
    *,
    image: str,
    title: str,
    is_video: bool,
    requester_id: int,
    playback_chat_id: int | None = None,
    info_url: str | None = None,
    duration: str | None = None,
):
    target_id = playback_chat_id if playback_chat_id is not None else chat_id
    label = "عنوان الفيديو" if is_video else "عنوان المقطع"
    blocks: list[dict[str, Any]] = [
        {"type": "heading", "text": "📡 بدأ البث 💡", "size": 1},
        {"type": "divider"},
        {"type": "photo", "photo": InputMediaPhoto(media=_media(image), parse_mode=None)},
        {"type": "divider"},
        {"type": "footer", "text": f"{label}: {title}"},
        {"type": "footer", "text": _button("قائمة التحكم", callback_data=f"RICHCTRL {target_id}|{requester_id}", style="primary")},
    ]
    if target_id != chat_id:
        blocks.insert(-1, {"type": "footer", "text": f"وجهة البث: {target_id}"})
    if info_url:
        blocks.append({"type": "footer", "text": {"type": "url", "text": "معلومات أكثر", "url": info_url}})
    else:
        text = "معلومات أكثر"
        if duration:
            text += f" • المدة: {duration}"
        blocks.append({"type": "footer", "text": text})

    async with Bot(token=config.BOT_TOKEN) as bot:
        return await bot.send_rich_message(chat_id=chat_id, rich_message=InputRichMessage(blocks=blocks))


async def send_control_panel_ephemeral(
    chat_id: int,
    *,
    receiver_user_id: int,
    callback_query_id: str,
    requester_id: int,
    delivery_chat_id: int | None = None,
):
    destination = delivery_chat_id if delivery_chat_id is not None else chat_id
    def action(text: str, command: str, style: str | None = None):
        return {"text": _button(text, callback_data=f"RCTRL {command}|{chat_id}|{requester_id}", style=style), "align": "center", "valign": "middle"}

    rows = [
        [action("▶️ استئناف", "Resume", "success"), action("⏸ إيقاف مؤقت", "Pause", "primary")],
        [action("⏭ تخطي", "Skip", "primary"), action("⏹ إنهاء", "Stop", "danger")],
        [action("🔀 خلط", "Shuffle", "primary"), action("🔁 تكرار", "Loop", "primary")],
        [action("⏪ 10 ث", "1"), action("10 ث ⏩", "2")],
        [action("⏪ 30 ث", "3"), action("30 ث ⏩", "4")],
    ]
    rich = InputRichMessage(blocks=[
        {"type": "heading", "text": "🎛 قائمة التحكم", "size": 2},
        *([{"type": "footer", "text": f"وجهة البث: {chat_id}"}] if destination != chat_id else []),
        {"type": "divider"},
        {"type": "table", "cells": rows, "is_bordered": True, "is_compact": True},
    ])
    ephemeral = EphemeralMessageParameters(
        receiver_user_id=receiver_user_id,
        callback_query_id=callback_query_id,
        replace_callback_query_message=False,
    )
    async with Bot(token=config.BOT_TOKEN) as bot:
        return await bot.send_rich_message(
            chat_id=destination,
            rich_message=rich,
            ephemeral_message_parameters=ephemeral if destination < 0 else None,
        )
