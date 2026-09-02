
# Summary GPT Bot

An AI-powered text summarization Telegram bot that generates concise summaries of text, URLs, PDFs, videos from 1000+ supported websites, and podcasts.

---


## 💡 使用體驗流程

### 場景 1: 影片摘要 + 續問
```
👤 用戶: https://youtube.com/watch?v=xxx
🤖 Bot: [生成摘要，包含五個部分：容易懂、總結、觀點、摘要、FAQ]

👤 用戶: 影片中提到的第三個重點是什麼？
🤖 Bot: 💬 續問回答: [基於原內容回答具體問題]

👤 用戶: 那第一個和第三個有什麼關聯？
🤖 Bot: 💬 續問回答: [分析兩者關聯]

👤 用戶: /clear
🤖 Bot: ✅ 對話歷史已清除
```

### 場景 2: 切換語言
```
👤 用戶: /lang
🤖 Bot: [顯示當前語言與語言選擇按鈕]
       Current language: 繁體中文
       🇹🇼 繁體中文  🇬🇧 English

👤 用戶: [點擊 English]
🤖 Bot: ✅ Language switched to: English

👤 用戶: https://ted.com/talks/xxx
🤖 Bot: [以英文輸出摘要]
```

### 場景 3: Podcast 摘要
```
👤 用戶: https://pocketcasts.com/podcast/xxx
🤖 Bot: [自動識別為 podcast]
       [提取 RSS feed → 獲取最新 episode]
       [下載音頻 → Whisper 轉錄 → 生成摘要]

👤 用戶: 這集主要在討論什麼？
🤖 Bot: 💬 續問回答: [基於 podcast 內容回答]
```

### 場景 4: 查看對話狀態
```
👤 用戶: /context
🤖 Bot: 📋 當前對話上下文:
       🔗 來源: https://youtube.com/watch?v=xxx
       📅 時間: 2025-11-19 10:30:00
       💬 問答輪數: 3
       📝 內容長度: 45 paragraphs
```

### 場景 5: 切換 LLM 模型
```
👤 用戶: /model
🤖 Bot: 🤖 當前模型: gemini-flash-latest
       請選擇模型:
       [✅ gemini-flash-latest]
       [gpt-4o-mini]
       [gpt-4o]
       [claude-3-sonnet]

👤 用戶: [點擊 gpt-4o]
🤖 Bot: ✅ 模型已切換為: gpt-4o

👤 用戶: /model claude-3-sonnet
🤖 Bot: ✅ 模型已切換至: claude-3-sonnet
```

### 場景 6: 解答之書
```
👤 用戶: /boa
🤖 Bot: 📖 解答之書 Book of Answers

       你需要考慮其他方法
```

### 場景 7: 塔羅占卜
```
👤 用戶: /tarot 最近適合轉職嗎？
🤖 Bot: 🔮 【塔羅占卜 Tarot Reading】
       📖 牌陣：三張牌牌陣 (Three Cards)
       ❓ 問題：最近適合轉職嗎？

       🃏 【抽牌結果】
         • 【過去】：權杖三（正位）
         • 【現在】：戰車（正位） ✨(大阿爾克那)
         • 【未來】：聖杯二（正位）

       💡 【AI 深度解牌建議】
       [AI 提供之詳細分析與行動指引]
```

### 場景 8: 月老姻緣籤與生肖合婚
```
👤 用戶: /yiyu 我和對方適合在一起嗎？
🤖 Bot: 🌸 【月老姻緣籤詩】
       ❓ 問題：我和對方適合在一起嗎？

       📜 【抽得籤詩】：第 1 籤 【上上籤】
       「花開月滿，緣分宜以真誠相待。」

       💡 【AI 姻緣指引與解籤】
       [AI 提供之感情發展與溝通指引]

👤 用戶: /yiyu zodiac 1995 1998 我們合嗎？
🤖 Bot: 🌸 【月老生肖合婚測算】
       ❓ 問題：我們合嗎？

       🎎 【生肖配對結果】
         • 第一方：1995 年生（生肖屬 豬）
         • 第二方：1998 年生（生肖屬 虎）
       💫 契合關係：六合：互相扶持、容易建立默契
       📊 契合指數：88 分

       💡 【AI 感情合婚指引】
       [AI 提供之生肖互動與相處建議]
```

### 場景 9: 888box 雲端資產轉存與管理
```
👤 用戶: /box https://example.com/video.mp4 實用教學影片
🤖 Bot: ✅ 【888box 轉存成功】

       🆔 資源 ID：`52`
       🔗 CDN 直鏈：https://d36gp3xejpe77o.cloudfront.net/storage/video/2026/08/27/video.mp4
       🌐 分享頁面：https://box.david888.com/v/abcd1234

👤 用戶: /boxstats
🤖 Bot: 📊 【888box 資產統計】
       • 📦 總資產數：44
       • 🖼️ 圖片：11
       • 🎥 影片：9
       • 🎵 音訊：18
       • 📄 檔案：6
       🌐 主機位址：https://box.david888.com
```

### 場景 10: David888 Wiki 一鍵發布、2D 簡報與電子書模式
```
👤 用戶: /wiki
🤖 Bot: 📚 【David888 Wiki 發布成功】

       📝 頁面路徑：`summary-20260827-abc123`
       🌐 閱讀頁面：https://wiki.david888.com/share/hzwna9
       🖥️ 2D 簡報模式：https://wiki.david888.com/share/hzwna9/present
       📖 電子書模式：https://wiki.david888.com/share/hzwna9/book
       🎨 套用主題：`tokyo-night`

👤 用戶: /wikiread summary-20260827-abc123
🤖 Bot: 📖 【Wiki 頁面內容：`summary-20260827-abc123`】
       [顯示該 Wiki 頁面之 Markdown 原始內容]
```

### 場景 11: 🎛️ 底部 Quick Reply 互動選單與自然語言風格切換
```
👤 用戶: [傳送 YouTube 影片或新聞文章 URL]
🤖 Bot: 📌 [影片標題]
       
       ① 【容易懂 Easy Know】...
       ② 【總結 Overall Summary】...
       ③ 【觀點與評論 Viewpoints】...
       ④ 【重點條列 Key Points】...
       ⑤ 【測驗三題 3-Question Quiz】...
       💡 【推薦延伸續問 Suggested Follow-ups】
          1. ... 2. ... 3. ...
       ⓺ 【關鍵標籤 Hashtags】
       
       [按鈕: ⚡ 1分鐘極簡版]  [按鈕: 📊 結構化大綱]
       [按鈕: ❓ 核心 Q&A]     [按鈕: 📱 社群貼文風]
       [按鈕: 🎨 繪製概念圖]  [按鈕: 📚 發布至 Wiki]

👤 用戶: [點擊 📱 社群貼文風] 或 直接輸入「轉成社群貼文」
🤖 Bot: 🔥【這部影片徹底顛覆了我對 AI 的想像！】
       ...[社群爆款 Hook + 重點條列 + Emoji + Hashtags]
```

---

## 核心與新增功能

- **🎛️ 底部 Quick Reply 互動選單與無縫風格切換**：摘要下方自動附帶 6 大隨點隨轉按鈕（1分鐘極簡版、結構化大綱、核心 Q&A、社群貼文風、🎨 繪製概念圖、發布至 Wiki）；亦支援在聊天室直接以自然語言（如「轉社群風」、「給我大綱」、「畫概念圖」）自由切換！
- **⚡ 5 段式結構化摘要與推薦續問**：標準產出容易懂、總結、觀點評論、重點條列、測驗三題、💡 推薦 3 個深入續問問題，兼具深度與互動性。
- **David888 Wiki 知識庫發布（LLM 深度報告好讀版）**：整合 `https://wiki.david888.com/api`，當使用者交代 LLM 撰寫長篇分析報告時，LLM 會自動將完整 Markdown 發布至 David888 Wiki，並回傳排版優美的公開閱讀連結（`shareUrl`）與 Reveal 2D 簡報模式（`presentUrl`）；亦可透過 `/wiki` 手動一鍵發布或 `/wikiread` 遠端讀取。
- **自然 AI 對話與智慧意圖分流**：日常打字（問候、編程諮詢、問題解答、隨意聊天）會以自然流暢的 AI 助理模式對話，並保留最近對話上下文；只有發送 URL、上傳文件或明確要求總結時，才會啟動結構化摘要。
- **888box 雲端資產儲存庫**：整合 888box（主要節點：`https://box.david888.com`，自動備援節點：`https://box.glsoft.ai`、`https://box.aiurl.tw`），提供 `/box <URL> [標題]` 遠端轉存各類影片、音訊、文件、圖片，自動產出 CloudFront 高速 CDN 下載直鏈與 Web 分享頁面，並可用 `/boxstats` 即時查看儲存統計。
- **AnyDoc 高效能文件解析**：採用 Firecrawl Rust 引擎 `firecrawl-anydoc`（取代 MarkItDown），支援 PDF、Word (DOCX)、Excel (XLSX)、PowerPoint (PPTX)、EPUB、RTF、CSV 等文件極速轉為 Markdown 進行摘要。
- **塔羅占卜 (`/tarot`)**：支援單張、三張牌、鑽石、月亮、馬蹄鐵、塞爾特十字牌陣，提供抽牌正逆位展示與 AI 深度解牌指引。
- **月老姻緣與生肖合婚 (`/yiyu`)**：支援月老求籤解籤詩與出生年生肖契合度合婚測算。
- **Whisper ASR 時間戳聽寫**：調用 GROQ Whisper API，預設輸出 `[MM:SS]` 精確時間軸標記，並以 `.txt` 檔案直接下載。
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

---

## 🛠 安裝與部署步驟 (Installation)

為了應對 YouTube 最新的防機器人機制 (Sign in to confirm you're not a bot)，這個專案需要配合一個真實的 Chrome Docker 容器來提供即時的 Cookies 與 JS 挑戰解謎。

### 步驟 1: Clone 專案
```bash
git clone https://github.com/tbdavid2019/telegram-bot-summary.git
cd telegram-bot-summary
```

### 步驟 2: 設定環境變數
複製範例環境變數檔並填入你的金鑰：
```bash
cp example.env .env
nano .env  # 填入 TELEGRAM_TOKEN, LLM_API_KEY 等必要資訊
```

### 步驟 3: 啟動 Chrome 輔助容器 (關鍵)
執行內建的設定腳本，這會啟動一個 Headless Chrome 容器，並綁定資料夾 `/home/bitnami/chrome-data`：
```bash
chmod +x setup_chrome_container.sh
./setup_chrome_container.sh
```

### 步驟 4: 登入 YouTube 建立真實 Session
1. Chrome 容器啟動後，它會開啟一個 VNC/WebUI 介面在你的伺服器 Port `3000`。
2. 打開瀏覽器前往 `http://<你的伺服器IP>:3000`。
3. 在裡面打開 YouTube 首頁並**登入你的 Google 帳號**。
4. 隨便點播 1-2 部影片，確定能正常播放（這會讓系統產生足夠的驗證 Token）。
5. 完成後就可以關閉該 WebUI 網頁。

### 步驟 5: Build 並啟動 Telegram Bot
執行 `build.sh`，它會自動打包 Bot 並把剛剛 Chrome 的設定檔掛載進 Bot 容器中供 `yt-dlp` 使用：
```bash
./build.sh
```

🎉 **完成！你的 Bot 現在已經可以順利繞過 YouTube 的機器人驗證並生成摘要了！**

---

👉 [telegram 示範機器人 小濃縮](https://t.me/quantaar_bot)

---

## Features

- **7-Layer Defensive Security Architecture**：內建完整的 7 層安全審計防護，阻斷 SSRF（私有 IP/迴路/雲端中繼資料封鎖）、Prompt Injection 隔離標記、常數時間 Bearer Token 驗證、FastAPI 安全標頭、例外安全暫存檔生命週期清理與路徑穿越過濾。
- **Multi-Tier Fallback LLM Engine**：支援多級 LLM 容錯降級機制 (`LLM1` -> `LLM2` -> `LLM3` -> `Groq Fallback`)，當主要模型遭遇 HTTP 400、429 超流、500/503 或網路逾時，秒級自動切換備用端點，並自動修復 Google Gemini OpenAI 格式相容性。
- **Supports text**：處理純文本。
- **Supports URLs**：自動擷取各類網頁文章與新聞內容（基於 `trafilatura`）。
- **Supports Documents & PDFs**：採用 Firecrawl Rust 引擎 `AnyDoc`，全面支援 PDF、Word (`.docx`)、PowerPoint (`.pptx`)、Excel (`.xlsx`)、EPUB、RTF、CSV 等文件極速轉為 Markdown 並進行 AI 摘要。
- **Supports 1000+ Video Websites**：處理來自 YouTube、Vimeo、Bilibili、TikTok、Twitch 等 1000+ 影片網站的字幕及聽寫。
- **Whisper API**：自動轉錄無字幕的影片與音訊，預設附帶精確時間戳 (`[MM:SS]`) 標註。
- **Divination & Astrology**：內建塔羅牌占卜 (`/tarot`)、月老姻緣籤與生肖合婚 (`/yiyu`)。
- **Email Summaries**：自動將生成的摘要發送到郵箱。
- **Discord Webhook**：支援將摘要同步發送到 Discord 頻道。
- **Smart URL Detection**：智能檢測影片 URL 並自動選擇最佳處理方式。

---

## Usage 使用方法

以下為包含英文與繁體中文的設置指導。

### 📱 機器人命令

| 命令 | 說明 |
|------|------|
| /start | 確認機器人是否在線 |
| /help | 顯示幫助訊息 |
| /lang | 切換語言 (繁體中文 ⇄ English) |
| /model | 切換/列出 LLM 模型 |
| /tarot [牌陣] [問題] | 塔羅抽牌與 AI 深度解讀 (支援單張/三張/六角/塞爾特等牌陣) |
| /yiyu [模式] [問題] | 月老姻緣求籤與生肖合婚契合度測算 |
| /boa | 解答之書 Book of Answers |
| /context | 顯示當前對話上下文 |
| /clear | 清除對話歷史 |
| /yt2audio <URL> | 下載影片音頻 |
| /yt2text <URL> | 將影片轉成帶時間戳的逐字稿文字檔 (`.txt`) |
| /box <URL> [標題] | 將遠端影片、音訊、圖片、文件轉存至 888box 雲端 |
| /boxstats | 查看 888box 當前儲存的資產總數與分類統計 |
| /wiki [標題/內容] | 發布至 David888 Wiki 知識庫 (產出公開好讀版與投影片) |
| /wikiread <路徑> | 讀取 David888 Wiki 頁面內容 |

### 💡 使用技巧

1. **直接發送內容**: 文字、網址、各類文件檔案（PDF、Word、Excel、PPT、EPUB、CSV、TXT）直接拖曳傳送即可自動摘要，無需輸入命令。
2. **續問功能**: 完成摘要後，直接發送問題即可續問
3. **語言切換**: 使用 `/lang` 切換語言後，之後的摘要都使用新語言
4. **多輪對話**: 系統自動保留最近 3 輪對話，支援深入討論
5. **新對話**: 發送新 URL 或 `/clear` 開始新的摘要

### Docker 設置指南

#### 影片處理

若要處理需要登入才能觀看的影片，請依照以下步驟：

在本地電腦執行以下命令來導出 cookies：

```bash
yt-dlp --cookies-from-browser chrome -F "視頻URL" --skip-download
```

將產生的 cookies.txt 檔案放入專案根目錄

#### 2. 自動化 Chrome Docker 方案 (推薦)

若您有運行中的 Chrome Docker 容器，可以使用自動化方案定期抓取並同步 cookies：

1. **運行 Chrome 容器**：使用 `linuxserver/chromium` 或類似映像檔。
2. **自動化指令**：
   - 確保 `chrome-data` 目錄已掛載。
   - 使用 `./extract_youtube_cookies.sh` 手動執行提取。
   - 腳本會自動將 cookies 同步到專案目錄並透過 Docker Volume 即時掛載給 Bot 使用。

詳細變更記錄請參閱 [Changelog](file:///home/bitnami/telegram-bot-summary/docs/changelog.md)。

#### 3. 拉取 Docker 映像
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

### LLM & Fallback Variables

| Environment Variable | Description |
|-----------------------|-------------|
| `LLM_API_KEY` / `OPENAI_API_KEY` | 主要 LLM API 金鑰 |
| `LLM_MODEL` | 主要 LLM 模型名稱 (預設: `gpt-4o-mini`) |
| `LLM_BASE_URL` | 主要 LLM API 基礎 URL (預設: `https://api.openai.com/v1`) |
| `LLM2_API_KEY` / `LLM2_MODEL` / `LLM2_BASE_URL` | 備用 LLM 2 設定 (支援自動容錯降級) |
| `LLM3_API_KEY` / `LLM3_MODEL` / `LLM3_BASE_URL` | 備用 LLM 3 設定 (支援多級容錯，可擴展至 LLM10) |
| `LLM_FALLBACK_MODELS` | 同節點備用模型列表 (逗號分隔) |
| `GROQ_API_KEY` | GROQ API 金鑰 (用於 Whisper 語音轉文字與自動 Groq LLM 降級) |
| `LLM_TIMEOUT_SECONDS` | LLM 呼叫逾時時間 (預設: `180` 秒) |

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

# Web API 配置 (用於 LLM / 外部系統 API 存取)
API_AUTH_TOKENS=your_api_token_1,your_api_token_2
API_PORT=8001

---

## 🌐 Web API 服務與 LLM Skill 整合

本專案除了提供 Telegram Bot 介面外，亦內建了高效率的 **FastAPI Web 服務**，能讓任何外部 LLM（如 Custom GPTs、Claude Projects、LangChain / LlamaIndex 代理）或第三方應用系統直接經由 HTTP POST 取得結構化的 Markdown 摘要。

### 1. 環境變數設定 (`.env`)

在 `.env` 中加入以下設定即可啟用或配置 API 存取：

| 環境變數 | 說明 | 預設值 / 範例 |
| --- | --- | --- |
| `API_AUTH_TOKENS` | API 金鑰驗證清單（多組請用逗號分隔） | `token1,token2,token3` |
| `API_PORT` | Web API 服務監聽埠 | `8001` |
| `WEB_REQUEST_TIMEOUT_SECONDS` | Webhook、SMTP 等一般外部服務的最長等待秒數 | `60` |
| `LLM_TIMEOUT_SECONDS` | 單次 LLM 摘要/問答呼叫的最長等待秒數 | `180` |
| `ASR_TIMEOUT_SECONDS` | 每段 Whisper ASR 轉錄的最長等待秒數 | `600` |
| `MEDIA_DOWNLOAD_TIMEOUT_SECONDS` | Podcast/影片音訊下載的最長等待秒數 | `900` |
| `MONGO_TIMEOUT_MS` | MongoDB 連線逾時毫秒數 | `5000` |

> 💡 *若未設定 `API_AUTH_TOKENS`，系統會在啟動時於容器 Log 中動態產生一組隨機的安全 Token。*

> 💡 *若 `MONGO_URI` 留空，Bot 會略過摘要儲存，仍會正常回覆 Telegram 與 API 請求。*

### 2. API 端點規格

#### 外部端點 (Default Port: `8001`)

* **`GET /health`**：健康檢查
* **`POST /api/v1/summarize`**：發送摘要請求
  * **Header**: `Authorization: Bearer <API_AUTH_TOKEN>`
  * **Body (JSON)**:
    ```json
    {
      "input": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "language": "zh-TW"
    }
    ```
  * **Response (JSON)**:
    ```json
    {
      "status": "success",
      "title": "影片標題或網頁標題",
      "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "summary": "# ⓵ 【容易懂 Easy Know】\n..."
    }
    ```

### 3. LLM 介接 (SKILL.md)

專案根目錄下附有專門為 LLM 說明的指令檔 [`SKILL.md`](file:///home/bitnami/telegram-bot-summary/SKILL.md)，包含完整請求格式與 **OpenAPI 3.0 YAML** 規格，可直接匯入 OpenAI Custom GPTs Actions 或 Prompt 系統。
