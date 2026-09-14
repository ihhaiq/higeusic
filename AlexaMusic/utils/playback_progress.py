"""Non-blocking progress updates for slow media preparation."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable
from typing import TypeVar


T = TypeVar("T")
_FRAMES = ("◐", "◓", "◑", "◒")


def format_elapsed(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


async def _update_progress(
    message,
    *,
    video: bool,
    initial_delay: float,
    interval: float,
) -> None:
    loop = asyncio.get_running_loop()
    started = loop.time()
    await asyncio.sleep(initial_delay)
    media_label = "الفيديو" if video else "الصوت"
    failures = 0
    frame_index = 0

    while True:
        elapsed = format_elapsed(loop.time() - started)
        text = (
            f"{_FRAMES[frame_index % len(_FRAMES)]} جارٍ تجهيز {media_label}، "
            "البوت يعمل ولم يتجمد.\n"
            f"⏱ الوقت المنقضي: `{elapsed}`"
        )
        try:
            await message.edit_text(text)
            failures = 0
        except asyncio.CancelledError:
            raise
        except Exception:
            failures += 1
            if failures >= 3:
                return
        frame_index += 1
        await asyncio.sleep(interval)


async def run_with_progress(
    message,
    operation: Awaitable[T],
    *,
    video: bool,
    initial_delay: float = 8,
    interval: float = 10,
) -> T:
    """Run an operation while periodically updating its Telegram message."""
    if message is None:
        return await operation

    progress_task = asyncio.create_task(
        _update_progress(
            message,
            video=video,
            initial_delay=initial_delay,
            interval=interval,
        )
    )
    try:
        return await operation
    finally:
        progress_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await progress_task
