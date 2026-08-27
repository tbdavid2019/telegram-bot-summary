# Changelog

## [2026-08-27] - Whisper ASR Timestamps & Multi-Format Documents

### ✨ Added & Improved
- **Whisper ASR 預設時間戳標註**:
  - Groq Whisper ASR API 升級使用 `response_format=verbose_json`，自動精準提取每一語句的時間區段 (`start`, `end`)。
  - 預設於逐字稿與音訊轉文字中標註 `[MM:SS]` / `[HH:MM:SS]` 時間軸標記。
  - 封裝 `format_timestamp` 與 `format_whisper_segments` 於 `app/services/content.py` 並建立完整單元測試。
  - 於 `/yt2text` 及音訊轉錄中直接以 `.txt` 檔案格式提供帶時間軸之全文逐字稿。

## [2026-08-26] - AnyDoc Document Engine & Tarot / Yinyuan Divination

### 🔄 Changed & Improved
- **AnyDoc 高效能文件解析引擎 (取代 MarkItDown)**:
  - 拔除並徹底移除 `markitdown[all]` 依賴。
  - 改用 Firecrawl 推出的 Rust 高效能文件解析庫 **`firecrawl-anydoc`** (`anydoc`)。
  - 大幅提升文件轉換速度（毫秒級），並支援 PDF、Word (.docx)、PowerPoint (.pptx)、Excel (.xlsx)、EPUB、RTF、CSV 及純文字等多種格式轉換為乾淨的 Markdown 進行 LLM 摘要。
  - 封裝為 `convert_document_to_markdown` 於 `app/services/content.py`，具備文字自動 fallback 機制與非同步線程保護。

### ✨ Added
- **塔羅占卜 (`/tarot`)**:
  - 串接 `qi.david888.com` 之 `POST /api/tarot-question`。
  - 支援 `single`（單張）、`three`（三張牌，預設）、`diamond`（鑽石）、`moon`（月亮）、`horseshoe`（馬蹄鐵）、`celtic`（塞爾特十字）牌陣與中文別名。
  - 輸出格式包含牌陣名稱、抽得牌組（正逆位、大阿爾克那標記）與 AI 深度解牌建議。
- **月老姻緣與生肖合婚 (`/yiyu`, `/yinyuan`)**:
  - 串接 `qi.david888.com` 之 `POST /api/yinyuan-question`。
  - 預設月老姻緣籤（`fortune`）問答，並支援生肖合婚模式（`zodiac`）。
  - 輸出籤詩詩句或生肖契合度指數，並由 AI 提供感情相處與合婚指引。
- **指令示範與說明**:
  - 用戶輸入 `/tarot` 或 `/yiyu` 未帶參數時，自動顯示清楚的操作格式與示範範例。
  - 同步更新 Telegram 選單指令列表 (`set_my_commands`) 與 `/help`。

## [2026-07-23] - Long Media Timeout Controls & Non-Blocking Summary Processing

### 🚀 Improved
- **Long YouTube/Podcast Processing**: Split external time limits by operation so long media work is not constrained by the short general network timeout.
  - `LLM_TIMEOUT_SECONDS=180` for a single summary or follow-up request.
  - `ASR_TIMEOUT_SECONDS=600` for each Whisper audio chunk.
  - `MEDIA_DOWNLOAD_TIMEOUT_SECONDS=900` for media downloads.
  - `WEB_REQUEST_TIMEOUT_SECONDS=60` for webhooks and SMTP.
- **Backward Compatibility**: Existing `HTTP_TIMEOUT_SECONDS` and `SUBPROCESS_TIMEOUT_SECONDS` values remain accepted as fallbacks for the renamed general-web and ASR settings.

### 🔧 Fixed
- **Event-loop Blocking**: Moved synchronous extraction, yt-dlp audio download, ASR, LLM, file conversion, MongoDB persistence, email, and Discord delivery off the Telegram/FastAPI event loop.
- **Optional MongoDB**: Leaving `MONGO_URI` empty now disables persistence instead of attempting a default MongoDB connection.
- **Docker Runtime Helper**: Added `runtime.py` to the container image so the application starts successfully after the non-blocking runtime update.

## [2026-07-21] - Expose Authenticated Web API & LLM Integration (Option B)

### ✨ Added
- **FastAPI Web App (`api.py`)**: Built an API service enabling programmatic content summary (YouTube videos, podcasts, web links, or raw text) via HTTP POST.
- **Multiple Token Auth (`API_AUTH_TOKENS`)**: Secured API endpoints with Bearer Token validation, supporting multiple comma-separated keys. Employs dynamic fallback token generation if unconfigured.
- **LLM Skill Definition (`SKILL.md`)**: Documented the API usage instructions, JSON schemas, and an OpenAPI 3.0 specification for seamless integration with other LLMs or Custom GPTs.

### 🚀 Improved
- **Unified Process Execution (Option B)**: Configured python-telegram-bot's asynchronous event loop to run side-by-side with FastAPI's Uvicorn server in a single container.
- **Exposed API Port**: Modified `Dockerfile`, `build.sh`, and `auto_update_ytdlp.sh` to expose and map container port `8001` to the host.

## [2026-04-16] - Auto-Update Script Fix & Cookie Mount Cleanup

### 🔧 Fixed (CRITICAL)
- **Auto-Update Consistency**: Fixed an issue where the `auto_update_ytdlp.sh` script was overriding the Docker volume mounts and mapping an incorrect `cookies.txt` file instead of the actual Chrome data folder. This caused `yt-dlp` to fail reading cookies after a successful container rebuild.
  - **Resolution**: Updated `auto_update_ytdlp.sh` to mirror `build.sh` exactly, ensuring it mounts `-v /home/bitnami/chrome-data:/chrome-data` during the container start.

### 🧹 Removed
- **Redundant Cron Jobs**: Removed the `extract_youtube_cookies.sh` cron job, which was unnecessary since `yt-dlp` now directly reads the active browser profile from `/chrome-data` instead of a static `cookies.txt` file.

## [2026-04-15] - YouTube Anti-Bot Bypass & Cookie Sync Optimization

### 🔧 Fixed (CRITICAL)
- **YouTube Anti-Bot Bypass ("Sign in to confirm you're not a bot")**: 
  - Fixed an issue where YouTube blocked download requests even with `cookies.txt` provided. YouTube now strictly enforces JS challenges (PO Token) which plain cookie text files cannot fulfill.
  - **Resolution**:
    - Changed `build.sh` to mount the live Chrome profile directory (`/home/bitnami/chrome-data:/chrome-data`) instead of a static `cookies.txt`.
    - Updated `yt-dlp` configs in `main.py` to use `'cookiesfrombrowser': ('chrome', '/chrome-data/.config/google-chrome', None, None)` instead of `'cookiefile': './cookies.txt'`.
    - This allows `yt-dlp` (with the help of `deno`, which was already in the Dockerfile) to solve JavaScript API challenges live by directly reading Chrome's current state.

### ✨ Added
- **Docker Volume Mount**: The `telegram-bot-summary` container now mounts `cookies.txt` as a volume. This allows the bot to receive real-time cookie updates from the host without needing to rebuild the image or restart the container.
- **Chrome Docker Integration**: Automated extraction of cookies from a running Chrome container using `yt-dlp`.

### 🚀 Improved
- **Optimized Cookie Extraction**: Rewrote `extract_youtube_cookies.sh` to be significantly faster. It now uses a lightweight URL (`google.com`) and disables playlist metadata extraction, reducing execution time from minutes to seconds.
- **Robustness**: Added file existence and size checks in the extraction script to prevent overwriting valid cookies with empty ones.
- **Permissions**: Added automatic `chmod 644` in the sync script to ensure the Docker container has read access to the mounted cookie file.

### 🔧 Fixed
- **Crontab Automation**: Fixed incorrect paths and formatting in the user crontab. Updated schedules to ensure `yt-dlp` updates and cookie extraction happen sequentially (3 AM and 4 AM).
- **Persistent Updates**: Updated `auto_update_ytdlp.sh` to include the volume mount, ensuring that the feature persists after automatic container updates.



## 📅 最新更新 (2025-12-03)

### ✨ 新功能

#### 1. LLM 模型切換功能 🤖
- 新增 `/model` 命令，可切換或列出可用的 LLM 模型
- 使用方式：
  - `/model` - 列出可用模型並顯示選擇按鈕
  - `/model gemini-flash-latest` - 直接切換到指定模型
- 可用模型由 `LLM_MODEL` 和 `LLM2_MODEL` 自動組成

#### 2. 解答之書 Book of Answers 📖
- 新增 `/boa` 命令，取回解答之書的智慧回答
- API 來源：answerbook.david888.com

#### 3. 環境變數重構 🔧
- `OPENAI_API_KEY` 重新命名為 `LLM_API_KEY` (保留向後兼容)
- 新增 LLM2 備用模型支援 (`LLM2_API_KEY`, `LLM2_MODEL`, `LLM2_BASE_URL`)
- 新增 `ANSWER_BOOK_API` 環境變數

#### 4. 廣告過濾功能 🚫
- System Prompt 更新，自動識別並略過 YouTuber 業配廣告
- 包括：VPN 推廣、訂閱服務、App 推廣、折扣碼等

#### 5. 代碼清理 🧹
- 移除未使用的 imports (`duckduckgo_search`, `tqdm`, `ThreadPoolExecutor`, `webvtt`)
- 移除未使用的函數和變數

---

## 📅 過往更新 (2025-11-19)

### ✨ 新功能

#### 1. 多語言支援 🌍
- 支援繁體中文和英文兩種語言輸出
- 使用 `/lang` 命令隨時切換語言
- 語言設定自動保存,後續摘要使用選定語言

#### 2. LLM 續問功能 💬
- 完成摘要後可針對內容提問
- 自動保留原始內容和摘要,支援多輪對話
- 智能識別續問 vs 新摘要請求
- 使用 `/context` 查看對話狀態
- 使用 `/clear` 清除歷史開始新對話

#### 3. Podcast 平台支援 🎙️
- **Pocket Casts** - 支援 podcast 摘要
- **SoundOn** - 支援台灣本地 podcast 平台
- **Apple Podcast** - 通過 iTunes API 獲取 RSS feed
