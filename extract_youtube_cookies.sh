#!/bin/bash
# Description: Extract YouTube cookies from Chrome container and sync to Bot container
# Author: Antigravity

BOT_DIR="/home/bitnami/telegram-bot-summary"
CHROME_DATA_DIR="/home/bitnami/chrome-data"
CONTAINER_NAME="telegram-bot-summary"

echo "[$(date)] Starting cookie extraction..."

# 1. Update yt-dlp in the chrome container
echo "Updating yt-dlp in chrome container..."
docker exec chrome /lsiopy/bin/python3 -m pip install -q -U yt-dlp

# 2. Extract cookies (using a light URL to speed up)
echo "Extracting cookies from Chrome profile..."
docker exec chrome /lsiopy/bin/yt-dlp --cookies-from-browser chrome:/config/.config/google-chrome \
  --cookies /config/youtube_cookies.txt \
  --no-playlist --playlist-items 0 \
  --skip-download "https://www.google.com" > /dev/null 2>&1

# 3. Process the extracted file
if [ -s "$CHROME_DATA_DIR/youtube_cookies.txt" ]; then
    echo "Cookies extracted successfully. Syncing..."
    
    # Copy to bot directory
    cp "$CHROME_DATA_DIR/youtube_cookies.txt" "$BOT_DIR/cookies.txt"
    
    # Set permissions so the container can read it (644)
    chmod 644 "$BOT_DIR/cookies.txt"
    
    # Cleanup temporary file in chrome-data
    rm -f "$CHROME_DATA_DIR/youtube_cookies.txt"
    
    # Since we use volume mount, we don't strictly need to restart,
    # but doing it once ensures any stuck processes or cached handles are refreshed.
    # Optional: docker restart $CONTAINER_NAME
    
    echo "Done! The bot now has the newest cookies via volume mount."
else
    echo "Error: Failed to extract cookies or file is empty!"
    exit 1
fi
