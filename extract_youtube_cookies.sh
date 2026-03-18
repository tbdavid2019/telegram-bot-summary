#!/bin/bash
echo "Installing/Updating yt-dlp in the chrome container..."
docker exec chrome /lsiopy/bin/python3 -m pip install -q -U yt-dlp

echo "Extracting YouTube cookies from Chrome..."
docker exec chrome /lsiopy/bin/yt-dlp --cookies-from-browser chrome:/config/.config/google-chrome \
  --cookies /config/youtube_cookies.txt \
  --skip-download "https://www.youtube.com" > /dev/null 2>&1

if [ -f "/home/bitnami/chrome-data/youtube_cookies.txt" ]; then
    echo "Cookies extracted successfully. Copying to Telegram Bot..."
    cp /home/bitnami/chrome-data/youtube_cookies.txt /home/bitnami/telegram-bot-summary/cookies.txt
    rm /home/bitnami/chrome-data/youtube_cookies.txt
    
    echo "Restarting telegram-bot-summary container..."
    docker restart telegram-bot-summary
    
    echo "Done! The bot should now be able to download YouTube videos using the newest cookies."
else
    echo "Error: Failed to extract cookies! Make sure the chrome container is running and you have logged into YouTube."
fi
