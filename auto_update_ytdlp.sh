#!/bin/bash

# Configuration
CONTAINER_NAME="telegram-bot-summary"
DIR="/home/bitnami/telegram-bot-summary"
LOG_FILE="$DIR/auto_update.log"
IMAGE_TAG="tbdavid2019/telegram-bot-summary:latest"

# Logging function
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting yt-dlp update check..."

# 1. Get the latest yt-dlp pre-release version from PyPI
# Using curl and jq to fetch the latest version info. We look for versions because yt-dlp releases often.
LATEST_VERSION=$(curl -s "https://pypi.org/pypi/yt-dlp/json" | grep -o '"version":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -z "$LATEST_VERSION" ]; then
    log "Error: Could not fetch latest yt-dlp version from PyPI."
    exit 1
fi

log "Latest yt-dlp version on PyPI: $LATEST_VERSION"

# 2. Get the current yt-dlp version in the running container
# Only run this if the container is actually running
if [ "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    CURRENT_VERSION=$(docker run --rm --entrypoint=yt-dlp $IMAGE_TAG --version 2>/dev/null)
else
    # If container is not running, we set current version to "none" to force a build
    CURRENT_VERSION="none"
    log "Container not running, will build and start it."
fi

log "Current yt-dlp version in container: $CURRENT_VERSION"

# 3. Compare versions and rebuild if necessary
if [ "$LATEST_VERSION" != "$CURRENT_VERSION" ]; then
    log "Versions differ. Rebuilding container..."
    
    cd "$DIR" || exit 1
    
    # Rebuild image
    if docker build --no-cache -t $CONTAINER_NAME .; then
        log "Docker build successful."
    else
        log "Docker build failed!"
        exit 1
    fi
    
    # Stop and remove old container
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
    
    # Run new container
    if docker run -d --name $CONTAINER_NAME --restart unless-stopped --env-file .env $CONTAINER_NAME; then
         log "New container started successfully."
    else
         log "Failed to start new container!"
         exit 1
    fi
    
    # Tag and Push
    log "Tagging image $IMAGE_TAG..."
    docker tag $CONTAINER_NAME $IMAGE_TAG
    
    log "Pushing image..."
    if docker push $IMAGE_TAG; then
        log "Image pushed successfully."
    else
        log "Failed to push image!"
        # Don't exit here, the local container is already running fine.
    fi
    
    # Clean up dangling images to save space
    docker rmi $(docker images -f "dangling=true" -q) 2>/dev/null
    
    log "Update complete!"
else
    log "yt-dlp is up to date. No action needed."
fi
