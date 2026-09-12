#!/usr/bin/env bash
set -u

echo "[YouTube tools] Checking for a newer yt-dlp release..."

if python3 -m pip install \
    --disable-pip-version-check \
    --no-cache-dir \
    --upgrade "yt-dlp[default]"; then
    echo "[YouTube tools] yt-dlp update completed."
else
    echo "[YouTube tools] WARNING: yt-dlp update failed; continuing with the installed version." >&2
fi

if command -v yt-dlp >/dev/null 2>&1; then
    VERSION="$(yt-dlp --version 2>/dev/null || true)"
    if [ -n "${VERSION}" ]; then
        echo "[YouTube tools] active yt-dlp version: ${VERSION}"
    else
        echo "[YouTube tools] WARNING: unable to read yt-dlp version." >&2
    fi
else
    echo "[YouTube tools] WARNING: yt-dlp is not available on PATH." >&2
fi

exit 0
