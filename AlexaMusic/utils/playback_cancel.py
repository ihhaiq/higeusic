"""Cancellation registry for in-flight play/video preparation requests."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


@dataclass
class PlayOperation:
    task: asyncio.Task
    user_id: int
    chat_id: int


_operations: dict[str, PlayOperation] = {}


def register_play_operation(*, user_id: int, chat_id: int) -> str:
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("Play operation must run inside an asyncio task")

    token = uuid.uuid4().hex[:12]
    _operations[token] = PlayOperation(
        task=task,
        user_id=int(user_id),
        chat_id=int(chat_id),
    )

    def _cleanup(_):
        _operations.pop(token, None)

    task.add_done_callback(_cleanup)
    return token


def cancel_markup(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "✖️ إلغاء العملية",
                callback_data=f"PLAYCANCEL {token}",
            )
        ]]
    )


def cancel_play_operation(
    token: str,
    *,
    user_id: int,
    privileged_user_ids: set[int] | None = None,
) -> str:
    operation = _operations.get(token)
    if operation is None:
        return "missing"

    allowed = int(user_id) == operation.user_id
    if privileged_user_ids:
        allowed = allowed or int(user_id) in privileged_user_ids
    if not allowed:
        return "forbidden"

    _operations.pop(token, None)
    if not operation.task.done():
        operation.task.cancel()
    return "cancelled"
