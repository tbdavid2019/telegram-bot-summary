# Changelog

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