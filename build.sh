

# docker builder prune
# docker build -t telegram-bot-summary .

docker build --no-cache -t telegram-bot-summary .
docker stop telegram-bot-summary
docker rm telegram-bot-summary
docker run -d     --name telegram-bot-summary     --restart unless-stopped     --env-file .env     telegram-bot-summary

docker tag telegram-bot-summary tbdavid2019/telegram-bot-summary:latest
docker push tbdavid2019/telegram-bot-summary:latest


# docker run -d     --name telegram-bot-summary     --restart unless-stopped     --env-file .env    tbdavid2019/telegram-bot-summary:latest