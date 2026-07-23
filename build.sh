

# docker builder prune
# docker build -t telegram-bot-summary .
# docker build --no-cache -t telegram-bot-summary . && docker stop telegram-bot-summary && docker rm telegram-bot-summary && docker run -d --name telegram-bot-summary --restart unless-stopped --env-file .env telegram-bot-summary


#!/usr/bin/env sh
set -eu

docker build --no-cache -t telegram-bot-summary .

if [ "${DEPLOY_CONFIRM:-0}" != "1" ]; then
    echo "Image built. To replace the running container, run: DEPLOY_CONFIRM=1 ./build.sh"
    exit 0
fi

docker stop telegram-bot-summary 2>/dev/null || true
docker rm telegram-bot-summary 2>/dev/null || true

set -- docker run -d \
    --name telegram-bot-summary \
    --restart unless-stopped \
    --env-file .env

if [ -n "${CHROME_DATA_DIR:-}" ]; then
    set -- "$@" -v "$CHROME_DATA_DIR:/chrome-data"
elif [ -d /home/bitnami/chrome-data ]; then
    set -- "$@" -v /home/bitnami/chrome-data:/chrome-data
fi

set -- "$@" -p 8001:8001 telegram-bot-summary
"$@"

docker tag telegram-bot-summary tbdavid2019/telegram-bot-summary:latest
docker push tbdavid2019/telegram-bot-summary:latest


# docker run -d     --name telegram-bot-summary     --restart unless-stopped     --env-file .env    tbdavid2019/telegram-bot-summary:latest
