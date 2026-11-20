#!/usr/bin/env sh
set -eu

docker build --no-cache -t telegram-bot-summary .
docker tag telegram-bot-summary tbdavid2019/telegram-bot-summary:latest
docker tag telegram-bot-summary ghcr.io/tbdavid2019/telegram-bot-summary:latest

if [ "${DEPLOY_CONFIRM:-0}" != "1" ]; then
    echo "Image built. To replace the running container, run: DEPLOY_CONFIRM=1 ./build.sh"
    exit 0
fi

mkdir -p "$PWD/data"

docker stop telegram-bot-summary 2>/dev/null || true
docker rm telegram-bot-summary 2>/dev/null || true

set -- docker run -d \
    --name telegram-bot-summary \
    --restart unless-stopped \
    --label com.centurylinklabs.watchtower.enable=true \
    --label com.centurylinklabs.watchtower.scope=summary \
    --env-file .env \
    -v "$PWD/data:/app/data"

if [ -n "${CHROME_DATA_DIR:-}" ]; then
    set -- "$@" -v "$CHROME_DATA_DIR:/chrome-data"
elif [ -d "$HOME/chrome-data" ]; then
    set -- "$@" -v "$HOME/chrome-data:/chrome-data"
elif [ -d /home/bitnami/chrome-data ]; then
    set -- "$@" -v /home/bitnami/chrome-data:/chrome-data
fi

if [ -f "cookies.txt" ]; then
    set -- "$@" -v "$PWD/cookies.txt:/app/cookies.txt:ro"
fi

if [ -f ".env" ]; then
    HOST_API_PORT=$(grep -E '^API_PORT=' .env 2>/dev/null | tail -n 1 | cut -d '=' -f2- | tr -d '[:space:]"' || true)
fi
HOST_API_PORT="${API_PORT:-${HOST_API_PORT:-8001}}"

set -- "$@" -p "$HOST_API_PORT:$HOST_API_PORT" tbdavid2019/telegram-bot-summary:latest
"$@"

# Verify replacement container stays up and passes health check
sleep 3
if ! docker ps -q -f name="^telegram-bot-summary$" | grep -q .; then
    echo "ERROR: Replacement container telegram-bot-summary exited unexpectedly." >&2
    docker logs --tail 50 telegram-bot-summary >&2 || true
    exit 1
fi

docker push tbdavid2019/telegram-bot-summary:latest
docker push ghcr.io/tbdavid2019/telegram-bot-summary:latest
