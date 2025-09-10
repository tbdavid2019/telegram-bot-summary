
# Summary GPT Bot

An AI-powered text summarization Telegram bot that generates concise summaries of text, URLs, PDFs, and videos from 1000+ supported websites.

---

## 新增功能

- **泛化影片支援**：支援 1000+ 影片網站，包括 YouTube、Vimeo、Bilibili、Dailymotion、TikTok、Twitch、Facebook、Instagram 等。
- **Whisper 聽寫功能**：調用免費的 GROQ Whisper API，用於自動生成字幕。
- **無字幕處理**：當影片無字幕時，可以啟用聽力辨識生成字幕。
- **智能網站檢測**：自動檢測 URL 是否為支援的影片網站，並使用相應的處理方式。
- **郵件功能**：自動將摘要結果發送到指定的收件人或群組郵箱（可配置 SMTP）。
- **Discord Webhook**：可將摘要結果同步發送到 Discord 頻道。
- 使用 `.env` 文件簡化環境變數配置。
- **私有影片支援**：支援需要登入才能觀看的影片處理（通過 cookies.txt）。

---

## 支援的影片網站

本機器人基於 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 技術，支援超過 1000 個影片網站，包括但不限於：

### 🎥 主流影片平台
- **YouTube** (youtube.com, youtu.be)
- **Vimeo** (vimeo.com)
- **Dailymotion** (dailymotion.com)
- **Bilibili** (bilibili.com) - 支援中文字幕
- **TikTok** (tiktok.com)
- **Twitch** (twitch.tv) - 直播和錄播

### 📺 新聞媒體
- **BBC** (bbc.co.uk)
- **CNN** (cnn.com)
- **NBC** (nbc.com)
- **Reuters** (reuters.com)
- **Al Jazeera** (aljazeera.com)

### 🎓 教育平台
- **Khan Academy** (khanacademy.org)
- **Coursera** (coursera.org)
- **edX** (edx.org)
- **TED** (ted.com)

### 🎵 音樂平台
- **SoundCloud** (soundcloud.com)
- **Bandcamp** (bandcamp.com)
- **Spotify** (部分內容)

### 📱 社交媒體
- **Facebook** (facebook.com)
- **Instagram** (instagram.com)
- **Twitter** (twitter.com)
- **Reddit** (reddit.com)

### 🌍 國際媒體
- **各國電視台**和廣播公司
- **Archive.org** 檔案庫內容
- **政府機構**官方影片

完整支援清單請參考：[yt-dlp 支援網站列表](https://ytdl-org.github.io/youtube-dl/supportedsites.html)

---

## 示範帳號

Telegram bot 可濃縮文字、URL、PDF 和 YouTube 影片的重點摘要。

👉 [telegram 示範機器人 小濃縮](https://t.me/quantaar_bot)

---

## Features

- **Supports text**：處理純文本。
- **Supports URLs**：自動擷取網頁內容。
- **Supports PDFs**：可解析 PDF 檔案。
- **Supports 1000+ Video Websites**：處理來自 YouTube、Vimeo、Bilibili、TikTok、Twitch 等 1000+ 影片網站的字幕及聽寫。
- **Whisper API**：自動轉錄無字幕的影片（需啟用 `USE_AUDIO_FALLBACK`）。
- **Email Summaries**：自動將生成的摘要發送到郵箱。
- **Discord Webhook**：支援將摘要同步發送到 Discord 頻道。
- **Smart URL Detection**：智能檢測影片 URL 並自動選擇最佳處理方式。

---

## Usage 使用方法

以下為包含英文與繁體中文的設置指導。

### Docker 設置指南

#### 影片處理

若要處理需要登入才能觀看的影片，請依照以下步驟：

在本地電腦執行以下命令來導出 cookies：

```bash
yt-dlp --cookies-from-browser chrome -F "視頻URL" --skip-download
```

將產生的 cookies.txt 檔案放入專案根目錄


#### 1. 拉取 Docker 映像
從 Docker Hub 拉取映像，請執行以下命令：
```bash
docker pull tbdavid2019/telegram-bot-summary:latest
```

#### 2. 運行 Docker 容器
執行以下命令來運行容器，請根據需求替換 `<value>`。
```bash
docker run -d \
    --name summary-gpt-bot \
    --restart unless-stopped \
    --env-file example.env \
    tbdavid2019/telegram-bot-summary:latest
```

#### 3. 環境變數說明

以下為主要環境變數：

- `LLM_BASE_URL`：語言模型的 API 基本地址。
- `OPENAI_API_KEY`：OpenAI 的 API 金鑰。
- `GROQ_API_KEY`：GROQ 的 API 金鑰（用於 Whisper 功能）。
- `TELEGRAM_TOKEN`：Telegram Bot 的令牌。
- `USE_AUDIO_FALLBACK`：是否啟用無字幕影片處理（`1` 啟用，`0` 禁用）。
- `ENABLE_EMAIL`：是否啟用郵件發送功能（`1` 啟用，`0` 禁用）。
- `SMTP_SERVER`：SMTP 伺服器地址（如 Gmail）。
- `SMTP_PORT`：SMTP 伺服器端口（如 Gmail 默認為 465）。
- `SMTP_USER`：SMTP 用戶名（如 Gmail 地址）。
- `SMTP_PASSWORD`：SMTP 密碼（或應用專用密碼）。
- `ENABLE_DISCORD_WEBHOOK`：是否啟用 Discord Webhook 功能（`1` 啟用，`0` 禁用）。
- `DISCORD_WEBHOOK_URL`：Discord Webhook 的 URL 地址。

---

## 環境變數表格

### LLM Variables

| Environment Variable | Description                       |
|-----------------------|-----------------------------------|
| `LLM_BASE_URL`        | LLM API 的基本地址               |
| `OPENAI_API_KEY`      | 用於 OpenAI API 的金鑰           |
| `GROQ_API_KEY`        | 用於 GROQ Whisper 的 API 金鑰    |

### Bot Variables

| Environment Variable  | Description                                                        |
|------------------------|--------------------------------------------------------------------|
| `CHUNK_SIZE`          | 最大處理塊大小，默認值為 `2100`                                   |
| `LLM_MODEL`           | 語言模型，例如 `chatgpt-4o-latest` 或 `llama-3.1`                |
| `TELEGRAM_TOKEN`      | Telegram 機器人的 API 令牌                                        |
| `TS_LANG`             | 預設摘要語言，默認值為 `繁體中文`                                |
| `USE_AUDIO_FALLBACK`  | 是否啟用無字幕影片處理功能，`1` 表示啟用，`0` 表示禁用           |
| `ALLOWED_USERS`       | 允許使用機器人的用戶 ID 列表，用逗號分隔                          |
| `SHOW_PROCESSING`     | 是否顯示處理中訊息，`1` 表示啟用，`0` 表示禁用                   |

### SMTP Variables

| Environment Variable  | Description                                                        |
|------------------------|--------------------------------------------------------------------|
| `ENABLE_EMAIL`        | 是否啟用郵件發送功能，`1` 表示啟用，`0` 表示禁用                 |
| `SMTP_SERVER`         | SMTP 伺服器地址，例如 `smtp.gmail.com`                           |
| `SMTP_PORT`           | SMTP 伺服器端口，例如 `465`（SSL）                                |
| `SMTP_USER`           | SMTP 用戶名（通常是郵件地址）                                     |
| `SMTP_PASSWORD`       | SMTP 密碼（或應用專用密碼）                                       |
| `SMTP_CC_EMAILS`      | CC 收件人列表，用逗號分隔                                          |

### Discord Variables

| Environment Variable     | Description                                                     |
|---------------------------|-----------------------------------------------------------------|
| `ENABLE_DISCORD_WEBHOOK` | 是否啟用 Discord Webhook 功能，`1` 表示啟用，`0` 表示禁用      |
| `DISCORD_WEBHOOK_URL`    | Discord Webhook 的 URL 地址                                    |

### Database Variables

| Environment Variable  | Description                                                        |
|------------------------|--------------------------------------------------------------------|
| `MONGO_URI`           | MongoDB 連接字串，用於儲存摘要記錄                               |

---

## 範例 `.env`

請參考 `example.env` 文件，配置所需的環境變數。

---

## 更新 Docker 映像

當映像有新更新時，使用以下命令更新容器：

```bash
```bash
docker pull tbdavid2019/telegram-bot-summary:latest
docker stop summary-gpt-bot
docker rm summary-gpt-bot
docker run -d \
    --name summary-gpt-bot \
    --restart unless-stopped \
    --env-file example.env \
    tbdavid2019/telegram-bot-summary:latest
```

---

## 新增 `example.env`

以下為範例 `.env` 文件內容：

```env
# 基本設置
CHUNK_SIZE=8000
LLM_MODEL=gemini-2.0-flash-exp
USE_AUDIO_FALLBACK=1

# API 金鑰
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key

# Telegram 配置
TELEGRAM_TOKEN=your_telegram_bot_token
ALLOWED_USERS=123456789,987654321

# MongoDB 配置
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/

# 顯示處理中訊息 (1 啟用，0 禁用)
SHOW_PROCESSING=1

# LLM URL
LLM_BASE_URL=https://gemini.david888.com/v1

# SMTP 配置
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_email_password
SMTP_CC_EMAILS=cc1@gmail.com,cc2@gmail.com

# 啟用郵件發送功能 (1 啟用，0 禁用)
ENABLE_EMAIL=1
