docker build -t telegram-bot-summary .
docker tag telegram-bot-summary tbdavid2019/telegram-bot-summary:latest
docker push tbdavid2019/telegram-bot-summary:latest

docker run -d     --name telegram-bot-summary     --restart unless-stopped     --env-file .env     telegram-bot-summary