"""Last-resort media retrieval through a configurable Telegram downloader bot."""

import asyncio
import contextlib
import os
import uuid
from pathlib import Path
from typing import Any


class TelegramMediaFallbackError(RuntimeError):
    """Raised when the external Telegram media fallback cannot return a file."""


# Bot accounts cannot call messages.GetHistory. Incoming replies are routed
# here by the bot's regular update dispatcher instead.
_pending_replies: dict[tuple[int, int], tuple[str, asyncio.Queue[Any]]] = {}


def normalize_bot_username(value: str | None) -> str:
    return str(value or "").strip().lstrip("@").lower()


def build_downloader_command(command: str, bot_username: str, link: str) -> str:
    command_name = str(command or "").strip().split(maxsplit=1)[0]
    if not command_name:
        raise TelegramMediaFallbackError("External downloader command is empty")
    if not command_name.startswith("/"):
        command_name = f"/{command_name}"
    command_name = command_name.split("@", 1)[0]
    username = normalize_bot_username(bot_username)
    if not username:
        raise TelegramMediaFallbackError("External downloader bot username is empty")
    return f"{command_name}@{username} {link}"


def _reply_to_message_id(message: Any) -> int | None:
    direct_id = getattr(message, "reply_to_message_id", None)
    if direct_id:
        return int(direct_id)
    replied = getattr(message, "reply_to_message", None)
    replied_id = getattr(replied, "id", None)
    return int(replied_id) if replied_id else None


def _is_expected_media_reply(
    message: Any,
    *,
    command_message_id: int,
    bot_username: str,
) -> bool:
    sender = getattr(message, "from_user", None)
    sender_username = normalize_bot_username(getattr(sender, "username", None))
    if sender_username != normalize_bot_username(bot_username):
        return False
    if _reply_to_message_id(message) != int(command_message_id):
        return False
    return any(
        getattr(message, media_type, None)
        for media_type in ("audio", "video", "document")
    )


def route_telegram_media_fallback_reply(message: Any) -> bool:
    """Route an incoming Telegram update to its waiting downloader request."""
    chat = getattr(message, "chat", None)
    chat_id = getattr(chat, "id", None)
    reply_to_message_id = _reply_to_message_id(message)
    if chat_id is None or reply_to_message_id is None:
        return False

    pending = _pending_replies.get((int(chat_id), int(reply_to_message_id)))
    if pending is None:
        return False

    expected_username, queue = pending
    sender = getattr(message, "from_user", None)
    sender_username = normalize_bot_username(getattr(sender, "username", None))
    if sender_username != expected_username:
        return False

    queue.put_nowait(message)
    return True


async def _delete_messages(*messages: Any) -> None:
    for message in messages:
        if message is None:
            continue
        with contextlib.suppress(Exception):
            await message.delete()


async def fetch_media_from_telegram_bot(
    client: Any,
    *,
    source_chat_id: int,
    bot_username: str,
    command: str,
    link: str,
    request_chat_id: int,
    response_timeout: int = 180,
    download_timeout: int = 900,
    cleanup: bool = True,
) -> str:
    """Ask an external bot for a media file and download its correlated reply.

    Replies are accepted only when they come from the configured bot and reply
    directly to this request message. This keeps concurrent requests isolated.
    """
    if not source_chat_id:
        raise TelegramMediaFallbackError("External downloader chat ID is missing")

    request = await client.send_message(
        int(source_chat_id),
        build_downloader_command(command, bot_username, link),
        disable_web_page_preview=True,
    )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.1, float(response_timeout))
    last_reply_text = ""
    pending_key = (int(source_chat_id), int(request.id))
    reply_queue: asyncio.Queue[Any] = asyncio.Queue()
    _pending_replies[pending_key] = (
        normalize_bot_username(bot_username),
        reply_queue,
    )

    try:
        while loop.time() < deadline:
            remaining = deadline - loop.time()
            try:
                message = await asyncio.wait_for(
                    reply_queue.get(),
                    timeout=max(0.01, remaining),
                )
            except asyncio.TimeoutError:
                break

            if _is_expected_media_reply(
                message,
                command_message_id=request.id,
                bot_username=bot_username,
            ):
                target_dir = (
                    Path("downloads")
                    / f"telegram_fallback_{request_chat_id}_{uuid.uuid4().hex[:10]}"
                )
                target_dir.mkdir(parents=True, exist_ok=True)
                try:
                    downloaded = await asyncio.wait_for(
                        client.download_media(
                            message,
                            file_name=f"{target_dir}{os.sep}",
                        ),
                        timeout=max(60, int(download_timeout)),
                    )
                except asyncio.TimeoutError as error:
                    raise TelegramMediaFallbackError(
                        "Timed out while downloading the external bot result"
                    ) from error
                if not downloaded:
                    raise TelegramMediaFallbackError(
                        "External downloader returned media but download failed"
                    )
                if cleanup:
                    await _delete_messages(message, request)
                return str(downloaded)

            reply_text = getattr(message, "text", None) or getattr(
                message, "caption", None
            )
            if reply_text:
                last_reply_text = str(reply_text).replace("\n", " ")[:300]
    finally:
        _pending_replies.pop(pending_key, None)
        if cleanup:
            await _delete_messages(request)

    detail = f": {last_reply_text}" if last_reply_text else ""
    raise TelegramMediaFallbackError(
        f"External downloader bot did not return a media reply in time{detail}"
    )
