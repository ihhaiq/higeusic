from __future__ import annotations

import re

VIDEO_COMMANDS = frozenset(
    {
        "vplay",
        "cvplay",
        "vplayforce",
        "cvplayforce",
        "فيديو",
    }
)


def normalize_command(value: object) -> str:
    """Return a command name without a prefix or ``@bot`` suffix."""
    command = str(value or "").strip().casefold()
    command = command.lstrip("/!.")
    return command.split("@", 1)[0]


def play_command_name(message) -> str:
    command = getattr(message, "command", None) or []
    if command:
        return normalize_command(command[0])
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return normalize_command(text.split(None, 1)[0] if text else "")


def is_video_request(message) -> bool:
    """Detect explicit video commands and a standalone ``-v`` option."""
    if play_command_name(message) in VIDEO_COMMANDS:
        return True
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return "-v" in re.split(r"\s+", text.casefold().strip())
