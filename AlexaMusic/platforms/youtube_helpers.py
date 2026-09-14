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
    """Build public-video fallbacks first and keep account cookies last."""
    clients = parse_player_clients(player_clients)
    attempts: list[YouTubeAttempt] = []

    # bgutil's recommended path is mweb with an automatically bound PO Token.
    if pot_enabled and "mweb" in clients:
        attempts.append(
            YouTubeAttempt(
                YouTubeAuthStrategy.PO_TOKEN,
                use_plugins=True,
                use_cookies=False,
                player_client="mweb",
            )
        )

    # Preserve yt-dlp's own default client selection.  This is intentionally
    # different from an explicit web_safari attempt and restores the reliable
    # audio path used before the specialized fallbacks were introduced.
    attempts.append(
        YouTubeAttempt(
            YouTubeAuthStrategy.ANONYMOUS,
            use_plugins=False,
            use_cookies=False,
            player_client=None,
        )
    )

    # web_safari can expose HLS without a GVS PO Token. Keep the remaining
    # configured clients as additional isolated fallbacks for public videos.
    anonymous_clients = tuple(client for client in clients if client != "mweb")
    if not anonymous_clients and not pot_enabled:
        anonymous_clients = clients
    for client in anonymous_clients:
        attempts.append(
            YouTubeAttempt(
                YouTubeAuthStrategy.ANONYMOUS,
                use_plugins=False,
                use_cookies=False,
                player_client=client,
            )
        )

    # Cookies are intentionally last: public playback must not depend on a
    # frequently expiring account session.
    if has_cookies:
        attempts.append(
            YouTubeAttempt(
                YouTubeAuthStrategy.COOKIES,
                use_plugins=False,
                use_cookies=True,
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
            "http error 403",
            "403 forbidden",
            "requested format is not available",
        )
    ):
        return "http_403"
    if any(
        marker in text
        for marker in (
            "too many requests",
            "http error 429",
            "rate limit",
        )
    ):
        return "rate_limited"
    if any(
        marker in text
        for marker in (
            "po token",
            "pot provider",
            "youtubepot",
        )
    ):
        return "po_token_failed"
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
    if any(
        marker in text
        for marker in ("no audio source found", "no video source found")
    ):
        return "stream_unavailable"
    return "unknown"


def friendly_youtube_error(error: object) -> str:
    category = classify_youtube_error(error)
    if category == "private":
        return "هذا الفيديو خاص ولا يمكن للبوت تشغيله."
    if category == "age_restricted":
        return "هذا الفيديو مقيّد بالعمر، ولم تنجح محاولة Cookies المصرح بها."
    if category == "cookies_rejected":
        return (
            "رفض YouTube طلب الخادم حتى بعد تجربة مسارات التشغيل العامة. "
            "الفيديوهات الخاصة أو المقيّدة فقط قد تحتاج Cookies صالحة."
        )
    if category == "http_403":
        return "رفض YouTube رابط الوسائط (403) بعد تجربة مسارات تشغيل بديلة."
    if category == "rate_limited":
        return "قيّد YouTube طلبات عنوان الخادم مؤقتاً. جرّب بعد قليل."
    if category == "po_token_failed":
        return (
            "فشل مزوّد PO Token، وتمت تجربة المسارات العامة البديلة دون نجاح."
        )
    if category == "live_unavailable":
        return "لا يمكن استخراج البث المباشر حالياً؛ قد يكون غير مباشر الآن أو انتهى."
    if category == "unavailable":
        return "فيديو YouTube غير متاح في الوقت الحالي أو في موقع الخادم."
    if category == "stream_unavailable":
        return (
            "تعذر فتح رابط الوسائط المستخرج من YouTube. "
            "تمت تجربة مسارات تشغيل بديلة ولم ينجح أي منها."
        )
    return "تعذر استخراج فيديو YouTube بعد تجربة PO Token والمسارات العامة وCookies الاختيارية."
