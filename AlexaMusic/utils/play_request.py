from __future__ import annotations

import re
from dataclasses import dataclass

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


@dataclass(frozen=True)
class PrivateVideoRequest:
    target: str | int
    query: str


def parse_private_video_request(message) -> PrivateVideoRequest:
    """Keep the destination out of the media search, including reply commands."""
    text = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    parts = text.split(None, 2)
    if len(parts) < 2:
        raise ValueError("missing destination")
    target = parts[1]
    if re.fullmatch(r"-\d+", target) and int(target) < 0:
        target = int(target)
    elif not re.fullmatch(r"@[A-Za-z0-9_]{1,32}", target):
        raise ValueError("destination must be a chat username or negative ID")
    return PrivateVideoRequest(target, parts[2].strip() if len(parts) > 2 else "")
