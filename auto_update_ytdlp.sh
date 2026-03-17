#!/bin/bash
set -euo pipefail

CONTAINER_NAME="telegram-bot-summary"
DIR="/home/bitnami/telegram-bot-summary"
LOG_FILE="$DIR/auto_update.log"
IMAGE_TAG="tbdavid2019/telegram-bot-summary:latest"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

normalize_version() {
    python3 - "$1" <<'PY'
import sys
from pkg_resources import parse_version
print(parse_version(sys.argv[1]))
PY
}

latest_pypi_prerelease() {
    python3 <<'PY'
import json
import urllib.request
from pkg_resources import parse_version
with urllib.request.urlopen("https://pypi.org/pypi/yt-dlp/json", timeout=20) as r:
    data = json.load(r)
versions = [v for v, files in data.get("releases", {}).items() if files]
versions.sort(key=parse_version, reverse=True)
print(versions[0] if versions else "")
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
        CURRENT_VERSION=$(docker run --rm --entrypoint=yt-dlp "$IMAGE_TAG" --version 2>/dev/null || echo "none")
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
    log "Versions differ. Rebuilding container..."
    cd "$DIR"

    if docker build --no-cache -t "$CONTAINER_NAME" .; then
        log "Docker build successful."
    else
        log "Docker build failed!"
        exit 1
    fi

    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true

    if docker run -d --name "$CONTAINER_NAME" --restart unless-stopped --env-file .env "$CONTAINER_NAME"; then
         log "New container started successfully."
    else
         log "Failed to start new container!"
         exit 1
    fi

    log "Tagging image $IMAGE_TAG..."
    docker tag "$CONTAINER_NAME" "$IMAGE_TAG"

    log "Pushing image..."
    if docker push "$IMAGE_TAG"; then
        log "Image pushed successfully."
    else
        log "Failed to push image!"
    fi

    DANGLES=$(docker images -f "dangling=true" -q)
    if [ -n "$DANGLES" ]; then
        docker rmi $DANGLES || true
    fi

    log "Update complete!"
else
    log "yt-dlp is up to date. No action needed."
fi
