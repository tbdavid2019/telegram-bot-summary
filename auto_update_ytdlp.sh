#!/bin/bash
set -euo pipefail

CONTAINER_NAME="telegram-bot-summary"
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$DIR/auto_update.log"
DOCKERHUB_IMAGE="tbdavid2019/telegram-bot-summary:latest"
GHCR_IMAGE="ghcr.io/tbdavid2019/telegram-bot-summary:latest"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

normalize_version() {
    if [ "$1" = "none" ] || [ -z "$1" ]; then
        echo "none"
        return 0
    fi
    python3 - "$1" <<'PY'
import re
import sys

raw = sys.argv[1].strip()
try:
    from packaging.version import Version
    print(Version(raw))
except Exception:
    print(re.sub(r"\.0+(\d+)", r".\1", raw.lstrip("v")))
PY
}

latest_pypi_prerelease() {
    python3 <<'PY'
import json
import urllib.request

with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=20) as r:
    data = json.load(r)

releases = [
    v
    for v, files in data.get("releases", {}).items()
    if files and any(not f.get("yanked", False) for f in files)
]
try:
    from packaging.version import Version
    releases.sort(key=Version, reverse=True)
except Exception:
    releases.sort(key=lambda s: [int(p) if p.isdigit() else 0 for p in s.replace("-", ".").split(".")], reverse=True)
print(releases[0] if releases else "")
PY
}

log "Starting yt-dlp update check..."
LATEST_VERSION=$(latest_pypi_prerelease)
if [ -z "$LATEST_VERSION" ]; then
    log "Error: Could not fetch latest yt-dlp version from PyPI releases."
    exit 1
fi
log "Latest yt-dlp version on PyPI releases: $LATEST_VERSION"

if docker ps -q -f name="^${CONTAINER_NAME}$" | grep -q .; then
    CURRENT_VERSION=$(docker exec "$CONTAINER_NAME" python3 -m yt_dlp --version 2>/dev/null || true)
    if [ -z "$CURRENT_VERSION" ]; then
        CURRENT_VERSION=$(docker run --rm --entrypoint=yt-dlp "$DOCKERHUB_IMAGE" --version 2>/dev/null || echo "none")
    fi
else
    CURRENT_VERSION="none"
    log "Container not running, will build and start it."
fi
log "Current yt-dlp version in container/image: $CURRENT_VERSION"

LATEST_NORM=$(normalize_version "$LATEST_VERSION")
CURRENT_NORM=$(normalize_version "$CURRENT_VERSION")
log "Normalized latest version: $LATEST_NORM"
log "Normalized current version: $CURRENT_NORM"

if [ "$LATEST_NORM" != "$CURRENT_NORM" ]; then
    log "Versions differ. Rebuilding and deploying container via build.sh..."
    cd "$DIR"

    if DEPLOY_CONFIRM=1 ./build.sh; then
        log "Build and deployment completed successfully."
    else
        log "Build/deployment failed!"
        exit 1
    fi

    DANGLES=$(docker images -f "dangling=true" -q)
    if [ -n "$DANGLES" ]; then
        docker rmi $DANGLES || true
    fi

    log "Update complete!"
else
    log "yt-dlp is up to date. No action needed."
fi
