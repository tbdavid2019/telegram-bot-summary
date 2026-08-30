# Changelog

## [2026-08-30] - Multi-Tier Fallback LLM Engine & Seamless High-Availability Failover

### ✨ Added
- **🛡️ 模組化多層級 LLM 容錯降級引擎 (`app/services/llm.py`)**:
  - 新增 `LLMEndpoint` 與 `call_llm_with_fallback()`，全面取代原本單點調用模式。
  - **自動探索多級模型端點與多 Key 金鑰池 (Multi-Tier & Multi-Key Discovery)**：
    - ① **Tier 1 (主要)**: `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` (支援多組逗號分隔金鑰自動輪詢容錯)
    - ② **Tier 2 (次要)**: `LLM2_API_KEY`, `LLM2_MODEL`, `LLM2_BASE_URL` (支援多組逗號分隔金鑰)
    - ③ **Tier 3~20 (超長延伸梯隊)**: `LLM3_*` 至 `LLM20_*` 自由擴展
    - ④ **JSON 結構化彈性備援池**: `LLM_FALLBACK_CONFIGS`（支援直接注入任意多組 provider、model 與 key）
    - ⑤ **同節點備用模型**: `LLM_FALLBACK_MODELS`
    - ⑥ **Groq 自動容錯池**: 當環境變數包含 `GROQ_API_KEY` / `GROQ_FALLBACK_KEYS` 且未手動指定 Groq LLM 時，自動掛載 `llama-3.3-70b-versatile` 作為自動容錯降級節點。
  - **智慧模型格式與別名容錯 (Model Normalization & Intra-Provider Alias Failover)**：
    - 自動處理 Google Gemini OpenAI 兼容端點（`generativelanguage.googleapis.com`）模型名稱（如將 `models/gemini-flash-latest` 自動轉譯為 `gemini-1.5-flash`，並在 400/404 時依序嘗試 `gemini-2.5-flash`、`gemini-2.0-flash`、`gemini-1.5-flash`）。
    - 自動處理 Groq 端點（`openai/gpt-oss-120b` 或 `llama-3.3-70b-versatile` 等模型別名防護）。
  - **高可用性自動故障轉移 (High-Availability Failover)**：
    - 當任何金鑰或端點遭遇 HTTP 400、401、403（金鑰失效/被封）、429（Rate Limit 額度超流）、500/503（服務癱瘓或超載）或網路連線逾時（Timeout）時，系統會立即無縫切換至同一梯隊的下一把 Key 或下一梯隊備用端點，保證用戶請求 100% 不中斷。
  - **全方位功能無縫受惠**：
    - 影片/網頁/文件摘要、Quick Reply 6 大風格轉換、繪製概念圖提示詞生成、問答續問、Tarot/Yinyuan 占卜命理解讀全面受惠於 Fallback 機制。

### 🔄 Changed & Improved
- **重構 `call_gpt_api` 與 `get_available_models`**:
  - `app/legacy.py`、`main.py` 與 `app/services/summarization.py` 全面遷移至 `app.services.llm`。
  - `/model` 命令與按鈕選單動態掃描所有啟用的 LLM 端點，使用者指定特定模型時若該模型出錯，亦會自動降級至備用模型。
- **單元測試全覆蓋 (`tests/test_llm.py`)**:
  - 增加 9 項新測試，涵蓋端點探索、Groq 自動備援、Google Gemini 相容性轉譯、HTTP 4xx/5xx 容錯切換、多層級連續故障轉移及使用者自選模型優先權，全測試通過率 100% (62/62)。


### ✨ Added & Improved
- **🎛️ 底部 Quick Reply 互動選單 (Inline Interactive Keyboard)**:
  - 獨立封裝 `app/services/quick_reply.py` 模組，於每次影音、文件、文章摘要後自動掛載 6 大隨點隨切快捷按鈕：
    - `⚡ 1分鐘極簡版`：提煉 3 句超精華結論 + 關鍵數據。
    - `📊 結構化大綱`：梳理樹狀階層與心智圖大綱。
    - `❓ 核心 Q&A`：拆解 5 個高含金量問答（Q1~Q5）。
    - `📱 社群貼文風`：轉換為自帶 Hook、Emoji 與 Hashtags 的高傳播力社群文案。
    - `🎨 繪製概念圖`：自動生成主題英文視覺 Prompt 並調用 Flux 生圖直接回傳高畫質圖片。
    - `📚 發布至 Wiki`：一鍵發布至 David888 Wiki 產生好讀版與投影片模式。
- **⚡ 5 段式結構化摘要升級 + 💡 推薦延伸續問**:
  - 全新設計繁中與英文 System Prompt，標準輸出：容易懂、總結、觀點評論、重點條列、測驗三題、💡 推薦 3 個啟發性延伸續問、Hashtags。
- **💬 自然語言風格無縫切換 (Natural Language Style Intent Detection)**:
  - 聊天室直接輸入「轉社群風」、「給我大綱」、「1分鐘版」、「問答」、「生圖」或針對內容提出深入續問，系統自動基於前次摘要上下文無縫切換或答覆。
- **🍪 智慧 Cookie 動態偵測與跨平台相容修復 (Dynamic Cookie Resolution)**:
  - 實作 `get_ytdlp_cookie_opts()` 函式，自動依序偵測：① Chrome Profile (`/chrome-data/.config/google-chrome`) ➔ ② Host 掛載之 `cookies.txt` (`/app/cookies.txt`) ➔ ③ 無 Cookie 預設模式。
  - 徹底解決主機未掛載 Chrome Profile 時 yt-dlp 誤報 `could not find chrome cookies database` 導致轉錄失敗的問題。
  - 更新 `build.sh` 與 `telegram-build.sh`，在容器啟動時自動掛載宿主機之 `cookies.txt`。
- **📚 David888 Wiki 規範全面升級 (SKILL.md Spec Alignment & Book Mode)**:
  - 嚴格實作首行 `# Title` 標題規範與自動淨化函式 `sanitize_wiki_markdown`，自動清除開頭無效聊天語句，確保 Open Graph 與 SEO 標題抓取 100% 正確。
  - 支援 `Content-Type: text/markdown; charset=UTF-8` 原生二進制發布與參數配置，杜絕長篇 JSON 跳脫異常。
  - 支援 `Accept: text/markdown` 內容協商讀取，直接取得乾淨 Markdown。
  - 新增 **📖 電子書模式 (`/book`)** 與 **🖥️ 2D 簡報模式 (`/present`)** 專屬 URL 輸出。
  - 新增無狀態 Markdown API 用戶端方法：`render_markdown` (`/api/markdown/render`)、`parse_web_to_markdown` (`/api/markdown/parse`)、`lint_markdown` (`/api/markdown/lint`)。

## [2026-08-27] - LLM Autonomous Wiki Publishing, Rich Greetings & Multi-Service Integration

### ✨ Added & Improved
- **LLM 自動發布深度分析報告至 David888 Wiki**:
  - 當用戶要求撰寫長篇深度分析、架構研究、教學導讀、對話劇本或各類報告時，LLM 生成的高品質 Markdown 內容將由系統自動發布至 `wiki.david888.com`。
  - 對話訊息除了提供精簡摘要外，自動附上美觀排版之線上閱讀連結 (`shareUrl`) 與 Reveal 2D 簡報模式 (`presentUrl`)。
- **防止模型偽工具調用標籤外洩 (Output Sanitization & Tool Call Interceptor)**:
  - 封裝 `sanitize_model_output` 與 `is_wiki_or_report_request` 於 `app/services/content.py`。
  - 攔截並解析任何模型意外產生的 `[CALL:/wiki {...}]` 偽代碼標籤，自動提取內容完成發布，杜絕 raw JSON 洩漏到 Telegram 聊天視窗。
- **Watchtower 全自動持續部署修正與上線 (Automated Continuous Deployment)**:
  - 修正 `git.glsoft.ai` 上 Watchtower 之前開啟 `WATCHTOWER_LABEL_ENABLE=true` 導致未標記容器被略過的問題。
  - 在 `aicreate360.com` 與 `git.glsoft.ai` 雙伺服器正式安裝並啟用 Watchtower，配置 `DOCKER_API_VERSION=1.45` 與 `WATCHTOWER_POLL_INTERVAL=60`。
  - 當 Docker Hub 發布新版映像檔時，兩台伺服器均會在 60 秒內自動拉取並重啟最新容器。
- **全新升級之招呼語與幫助指南 (`/start` & `/help`)**:
  - 全面更新 `/start` 歡迎訊息與各項核心功能指引。
  - 重新架構 `/help` 命令指南，依日常對話、文件摘要、Wiki 知識庫、888box 雲端、占卜命理分門別類，並附上清晰用法範例。
- **David888 Wiki 知識庫整合 (`app/services/wiki.py`)**:
  - 串接 `https://wiki.david888.com/api`，支援原生 Markdown 頁面發布、覆寫與讀取。
  - 新增指令 `/wiki [標題/內容]`：一鍵將剛生成的 AI 摘要或自訂 Markdown 發布至 David888 Wiki，並回傳極美閱讀版 (`shareUrl`) 與簡報模式 (`presentUrl`)。
  - 新增指令 `/wikiread <路徑>`：直接在 Telegram 讀取 Wiki 筆記與知識庫內容（支援長篇 Markdown 檔案傳送）。
  - 支援主題自定義（預設 `tokyo-night`）。
- **自然 AI 對話與智慧意圖分流 (Dual-Mode Chat & Summary)**:
  - 改善 Telegram Bot 訊息處理邏輯，不再將所有日常純文字強制套用 6 段式長文摘要格式。
  - 封裝 `is_conversation_followup`：精準區分「針對上一篇摘要的續問」與「全新獨立創作/Wiki 任務（如寫英語對話、商務劇本、寫程式碼）」，不再把全新創作誤判為舊文章續問或套用 6 段式總結。
  - 當用戶發送問候（如「你好」）、日常提問、程式開發諮詢或即時問答時，自動切換為自然流暢的 AI 對話模式。
  - 智慧保留多輪對話上下文（`chat_history`），支援上下文連貫聊天。
  - 當用戶發送網址（URL）、上傳檔案、或輸入帶有「總結/摘要/TLDR」關鍵字與超長文章時，則精準啟動完整結構化摘要。
- **888box 雲端資產儲存庫整合 (`app/services/box.py`)**:
  - 串接 888box API，支援本機檔案上傳 (`upload`) 與遠端 URL 轉存 (`upload_url`)。
  - **多節點自動故障轉移 (Failover)**：
    - 主要節點：`https://box.david888.com`
    - 備用節點 1：`https://box.glsoft.ai`
    - 備用節點 2：`https://box.aiurl.tw`
  - 自動生成 CloudFront CDN 高速下載直鏈與 888box Web 分享頁面。
  - 新增指令 `/box <URL> [標題]`：支援直接將遠端音訊、影片、文件、圖片轉存至 888box。
  - 新增指令 `/boxstats`：即時查看 888box 當前儲存的圖片、影片、音訊、檔案總數統計。
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
