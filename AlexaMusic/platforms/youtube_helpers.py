"""Pure helpers shared by the YouTube extractor and its tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

SUPPORTED_YOUTUBE_PLAYER_CLIENTS = ("mweb", "web_safari", "tv", "web")
DEFAULT_YOUTUBE_PLAYER_CLIENTS = SUPPORTED_YOUTUBE_PLAYER_CLIENTS


class YouTubeAuthStrategy(str, Enum):
    PO_TOKEN = "po_token"
    COOKIES = "cookies"
    ANONYMOUS = "anonymous"


@dataclass(frozen=True)
class YouTubeAttempt:
    strategy: YouTubeAuthStrategy
    use_plugins: bool
    use_cookies: bool
    player_client: str | None = None


def parse_player_clients(value: object) -> tuple[str, ...]:
    """Parse a safe, ordered, de-duplicated YouTube player-client list."""
    if isinstance(value, str):
        candidates = value.split(",")
    elif isinstance(value, (list, tuple)):
        candidates = value
    else:
        candidates = ()

    clients: list[str] = []
    seen: set[str] = set()
    for raw_client in candidates:
        try:
            client = str(raw_client).strip().lower()
        except Exception:
            continue
        if client not in SUPPORTED_YOUTUBE_PLAYER_CLIENTS or client in seen:
            continue
        seen.add(client)
        clients.append(client)
    return tuple(clients) or ("mweb",)


def cookie_file_available(path: object) -> bool:
    try:
        candidate = os.fspath(path)
        return bool(candidate) and os.path.isfile(candidate) and os.path.getsize(candidate) > 0
    except (OSError, TypeError, ValueError):
        return False


def is_youtube_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    if not candidate:
        return False
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    try:
        host = (urlparse(candidate).hostname or "").lower().rstrip(".")
    except ValueError:
        return False
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


def extraction_source(query: str, limit: int = 1) -> str:
    query = str(query).strip()
    return query if is_youtube_url(query) else f"ytsearch{max(1, int(limit))}:{query}"


def build_attempts(
    *,
    pot_enabled: bool,
    has_cookies: bool,
    player_clients: object = None,
) -> tuple[YouTubeAttempt, ...]:
    attempts: list[YouTubeAttempt] = []
    if pot_enabled:
        for client in parse_player_clients(player_clients):
            attempts.append(
                YouTubeAttempt(
                    YouTubeAuthStrategy.PO_TOKEN,
                    use_plugins=True,
                    use_cookies=False,
                    player_client=client,
                )
            )
    if has_cookies:
        attempts.append(
            YouTubeAttempt(
                YouTubeAuthStrategy.COOKIES,
                use_plugins=False,
                use_cookies=True,
            )
        )
    attempts.append(
        YouTubeAttempt(
            YouTubeAuthStrategy.ANONYMOUS,
            use_plugins=False,
            use_cookies=False,
        )
    )
    return tuple(attempts)


def duration_to_seconds(duration) -> int:
    if duration in (None, "", False):
        return 0
    if isinstance(duration, (int, float)):
        return max(0, int(duration))
    try:
        parts = [int(part) for part in str(duration).split(":")]
    except (TypeError, ValueError):
        return 0
    if not parts or len(parts) > 3 or any(part < 0 for part in parts):
        return 0
    total = 0
    for part in parts:
        total = total * 60 + part
    return total


def classify_youtube_error(error: object) -> str:
    text = str(error).lower()
    if any(marker in text for marker in ("private video", "this video is private")):
        return "private"
    if any(
        marker in text
        for marker in (
            "age-restricted",
            "age restricted",
            "confirm your age",
            "inappropriate content",
        )
    ):
        return "age_restricted"
    if any(
        marker in text
        for marker in (
            "sign in to confirm you’re not a bot",
            "sign in to confirm you're not a bot",
            "cookies are no longer valid",
            "account cookies have expired",
            "cookie file",
        )
    ):
        return "cookies_rejected"
    if any(
        marker in text
        for marker in (
            "live stream offline",
            "premieres in",
            "not currently live",
            "cannot extract live",
            "no video formats found",
        )
    ):
        return "live_unavailable"
    if any(
        marker in text
        for marker in ("video unavailable", "not available in your country")
    ):
        return "unavailable"
    return "unknown"


def friendly_youtube_error(error: object) -> str:
    category = classify_youtube_error(error)
    if category == "private":
        return "هذا الفيديو خاص ولا يمكن للبوت تشغيله."
    if category == "age_restricted":
        return "هذا الفيديو مقيّد بالعمر، ولم تنجح محاولة Cookies المصرح بها."
    if category == "cookies_rejected":
        return (
            "تعذر استخراج الفيديو من YouTube. يبدو أن YouTube طلب تسجيل الدخول "
            "أو رفض طلب الخادم. جرّب لاحقاً أو أضف Cookies صالحة من إعدادات السيرفر."
        )
    if category == "live_unavailable":
        return "لا يمكن استخراج البث المباشر حالياً؛ قد يكون غير مباشر الآن أو انتهى."
    if category == "unavailable":
        return "فيديو YouTube غير متاح في الوقت الحالي أو في موقع الخادم."
    return "تعذر استخراج فيديو YouTube بعد محاولات PO Token وCookies وAnonymous."
