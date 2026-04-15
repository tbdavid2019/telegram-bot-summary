#!/bin/bash
# Description: Set up the required standalone Chrome headless Docker container for telegram-bot-summary
# This provides cookies and JS challenge solving capabilities for yt-dlp.
# Author: Antigravity

CHROME_DATA_DIR="${HOME}/chrome-data"
CONTAINER_NAME="chrome"

echo "=========================================================="
echo " Setting up Headless Chrome Container for Telegram Bot"
echo "=========================================================="

# 1. Create data directory
echo "[1/4] Creating Chrome data directory at $CHROME_DATA_DIR..."
mkdir -p "$CHROME_DATA_DIR"
# Ensure permissions are correct so the container can write to it
chmod -R 777 "$CHROME_DATA_DIR"

# 2. Pull and run the Chrome image
echo "[2/4] Pulling and starting lscr.io/linuxserver/chromium image..."
# Use linuxserver/chromium as it has a built-in Python environment for yt-dlp cookie extraction
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

docker run -d \
  --name=$CONTAINER_NAME \
  --security-opt seccomp=unconfined \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Etc/UTC \
  -e CHROME_CLI=https://www.youtube.com \
  -v "$CHROME_DATA_DIR:/config" \
  --restart unless-stopped \
  lscr.io/linuxserver/chromium:latest

echo "[3/4] Installing yt-dlp inside the Chrome container..."
# Wait a few seconds for the container to fully initialize
sleep 5
docker exec $CONTAINER_NAME /lsiopy/bin/python3 -m pip install -q -U yt-dlp

echo "[4/4] Setup Complete!"
echo ""
echo "Next Steps:"
echo "1. The Chrome container is now running."
echo "2. You MUST log into YouTube using VNC (Port 5900) or WebUI (Port 3000)."
echo "   - Open your browser: http://<your_server_ip>:3000"
echo "   - Navigate to https://www.youtube.com and sign in to a Google account."
echo "   - Play a few videos to ensure cookies/tokens are generated."
echo "   - Close the browser tab inside the container."
echo "3. Run your Bot's build.sh"
echo "=========================================================="
