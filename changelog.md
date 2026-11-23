# Changelog

## [2026-11-23] - YouTube Channel/Playlist Guard, Explicit Rejection Diagnostics & Concurrent Queue Recovery

### ✨ Added
- **🛡️ YouTube 頻道／播放清單防呆攔截與可排查拒絕理由 (`app/services/content.py`, `app/legacy.py`)**:
  - 新增 `get_unsupported_media_url_reason(url)`，針對 YouTube 頻道首頁（`/channel/...`、`/@...`、`/c/...`、`/user/...`）、純播放清單（`/playlist?list=...` 且無 `v=`）及非影片首頁／分類頁（`/feed/...`、`/results` 等）直接攔截，並回傳清楚的使用者提示與排查代碼（`UNSUPPORTED_YOUTUBE_CHANNEL`、`UNSUPPORTED_YOUTUBE_PLAYLIST`、`UNSUPPORTED_YOUTUBE_PAGE`）及寫入 `logger.warning`，防止 `yt-dlp` 遞迴抓取整個頻道耗盡主機記憶體與阻塞佇列；同時允許帶有單支影片 ID 的連結（如 `watch?v=...&list=...`、`youtu.be/...`、`/shorts/...`、`/live/...`）正常處理。
  - 更新 `is_extraction_error()` 辨識診斷拒絕與逾時訊息，確保 `/yt2text` 不會將拒絕理由誤打包為 `transcript.txt`。

### 🔄 Changed & Improved
- **⚡ 啟用 Telegram 並發更新與單筆 URL 牆上時間逾時保護 (`app/legacy.py`, `app/api.py`, `example.env`, `README.md`)**:
  - `_build_bot_application()` 啟用 `.concurrent_updates(BOT_CONCURRENT_UPDATES)`（預設 `8`）並新增 `_on_application_error` 全域更新錯誤記錄器，避免單一慢速或異常 URL 阻塞後續正常排隊訊息。
  - `_build_ytdlp_opts()` 預設加入 `"noplaylist": True`；`is_supported_by_ytdlp()` 與 `get_video_title()` 改用 `extract_flat="in_playlist"` 及 `YTDLP_PROBE_TIMEOUT_SECONDS`（預設 `45s`），並於偵測到 `_type` 為 `playlist`/`multi_video` 時立即中止探測。
  - `handle("summarize", ...)`、`/yt2audio`、`/yt2text` 及 FastAPI `app/api.py` 均加上 `URL_PROCESSING_TIMEOUT_SECONDS`（預設 `900s`）牆上時間逾時保護；逾時時回傳明確診斷訊息（含 `URL_PROCESSING_TIMEOUT` 排查代碼，API 回傳 HTTP `504`）並釋放後續佇列繼續執行。
- **🧪 新增回歸測試 (`tests/test_content.py`, `tests/test_audit_fixes.py`)**:
  - 覆蓋頻道／播放清單／首頁攔截與單支影片放行、頻道網址不觸發 `yt_dlp.YoutubeDL` 與 `scrape_text_from_url`、逾時保護後回傳 `URL_PROCESSING_TIMEOUT` 且不阻塞後續正常 URL，以及 `concurrent_updates > 1` 驗證。

## [2026-11-20] - EGM Comprehensive Security, Reliability, Architecture & Docs Overhaul

### ✨ Added
- **🛡️ 安全強化與操作邊界防護 (`Dockerfile`, `.dockerignore`, `app/config.py`, `app/services/content.py`, `app/api.py`)**:
  - 新增 `.dockerignore` 並移除 `Dockerfile` 之 `COPY cookies.txt .` 與 CI `touch cookies.txt` 權宜作法，防止本機 cookies/secrets 打包進 Docker 映像層；加入 `HEALTHCHECK` 探針。
  - `app/config.py` 新增共用 `get_mongo_client()` 連線池、`is_admin_user()`（以 `ADMIN_USERS` 保護公開模式下之 `/box` 與 `/boxstats`）、可自訂之 `BOT_DISPLAY_NAME` / `BOT_TAGLINE` / `SUPPORT_CONTACT` 與 `/app/data` 持久化目錄探索。
  - `app/api.py` 新增 `/readyz` 就緒探針（檢查 MongoDB 與 Bot polling 狀態）、每 Token 滑動視窗 Rate Limit（`API_RATE_LIMIT_PER_MINUTE`，超限回傳 HTTP `429`）、請求歸因日誌與 `Cache-Control: no-store` 回應標頭。
  - `app/services/content.py` 新增 `safe_http_get()`（人工驗證每一跳 HTTP `3xx` redirect 目標防堵 SSRF）與共用 `EXTRACTION_ERROR_MESSAGES` / `is_extraction_error()` 錯誤判斷契約。
- **🧪 新增全方位回歸測試 (`tests/test_audit_fixes.py`)**:
  - 新增覆蓋 `SHOW_PROCESSING=0`、`/yt2audio` 與 `/yt2text` 白名單/SSRF/錯誤訊息、純圖片拒絕、`/box` 管理員隔離、長對話不誤發 Wiki、SSRF DNS Fail-Closed/CGNAT/Redirect、Wiki 路徑穿越、`/readyz` 與 API Rate Limit、`SummaryRepository` `bot_scope` 標籤與單次標題快取之測試。

### 🔄 Changed & Improved
- **🏗️ 消滅雙入口鏡像與整合服務層 (`app/legacy.py`, `main.py`, `api.py`, `runtime.py`, `app/services/summarization.py`, `app/services/podcast.py`)**:
  - 將根目錄 `main.py`、`api.py`、`runtime.py` 改為薄轉接 shim，消除 3,280+ 行手動同步重複碼；同步更新 `AGENTS.md` 與 `tests/test_async_boundaries.py`、`tests/test_main_runtime_guards.py`、`tests/test_decision.py`、`tests/test_runtime.py`。
  - 統一 `app/services/summarization.py` 為 Bot 與 FastAPI 唯一共用的 `summarize()` 實作；將 SoundOn/Apple Podcast/Pocket Casts RSS 解析與下載轉錄收斂至 `app/services/podcast.py`（改為 10 分鐘 TTL 快取與 500MB 下載上限）；抽出 `_finalize_and_deliver_summary()` 與 `_handle_quick_reply_action()` 簡化 `app/legacy.py`。
  - 統一 Groq Whisper ASR 管線至 `transcribe_local_audio()`：改用 `ffmpeg -f segment` 串流切分壓縮 MP3（免除整檔解碼 PCM 爆 RAM）、以 `requests.post` 取代 `curl` 子程序（杜絕 `/proc` 洩漏 `GROQ_API_KEY`）、支援多 Key 輪替與有界併發，並使用 `tempfile.TemporaryDirectory()` 消除 `/tmp` 併發覆蓋。
  - 加入單次請求 `_URL_TITLE_CACHE` 與 `_YTDLP_INFO_CACHE`，消除單一 URL 重複呼叫 4 次 `yt-dlp` 與 2 次網頁抓檔；支援 PTB `PicklePersistence`（搭配 `build.sh` `-v "$PWD/data:/app/data"`）保存對話與用戶設定；統一 `auto_update_ytdlp.sh` 委託 `DEPLOY_CONFIRM=1 ./build.sh` 確保 Watchtower labels 與 GHCR 同步。
  - 清理過時檔案：`main-andoird.py`、`scratch_test.py`、`extract_youtube_cookies.sh` 與重複之根目錄 `CHANGELOG.md`。

### 🔧 Fixed
- **🐛 修復多項功能、隱私隔離與雙審查（OMP & OpenCode）發現之 P1/P2/P3 缺陷**:
  - **SSRF DNS Rebinding 與傳輸上限防護 (`app/services/content.py`, `app/legacy.py`)**：在 `safe_http_get()` 內新增 `_SSRFPinnedConnectionGuard`，於實際 TCP `connect` 前再次檢驗 DNS 解析 IP 並阻擋非全域位址，並加入 10MB 回應體上限與總傳輸截止時間；`/yt2audio` 與 `/yt2text` 之 `is_safe_url()` 檢查亦改為非阻塞 `run_blocking` 執行，`download_video_audio()` 失敗時自動清除殘留暫存檔；`process_user_input()` 統一正規化 `www.` 開頭網址。
  - **Wiki 自動發布隱私與 API 驗證 (`app/services/content.py`, `app/legacy.py`, `app/services/wiki.py`)**：新增嚴格 `is_explicit_wiki_publish_request()`，日常對話包含「分析」「比較」等關鍵字不再自動公開發布至 Wiki；`publish_wiki_page()` / `append_wiki_page()` 修復路徑雙重 URL 編碼，並要求後端回傳有效非空 JSON 與真實網址/ID（移除非 JSON HTML 200 假成功與偽造 `shareUrl`）。
  - **FastAPI 安全性與可用性強化 (`app/api.py`, `app/config.py`, `app/services/api_keys.py`, `app/repositories/summaries.py`)**：加入認證前每 IP Rate Limit（阻絕無效 Token 與 DB/flock 暴力測試）、穩定 Owner 歸因與過期桶回收、`asyncio.Semaphore` 併發上限（`API_MAX_CONCURRENT_SUMMARIES`）、`200,000` 字元請求上限、移除日誌印出隨機 Token、`/readyz` 於 Bot 尚未就緒時正確回傳 HTTP `503`、`get_mongo_client()` 補齊 `socketTimeoutMS`、`rotate_key()` 改用 Mongo 原子 Compare-And-Swap、`APIKeyManager` 統一支援 `BOT_DATA_DIR`，並強制 `SummaryRepository` 覆寫寫入 `bot_scope`。
  - **聊天室狀態隔離與啟動韌性 (`app/legacy.py`)**：將 `conversation_history`、`chat_history` 與 `ad_hidden_*` 改存於 `context.chat_data`（各群組與私訊互不外洩），新增毀損 `bot_persistence.pkl` 啟動自動隔離備份並重建機制、`0o700` 目錄權限、`set_my_commands()` Token 遮罩與廣告提示改採跳脫 HTML。
  - **摘要、ASR、Podcast、決策快取與腳本修正 (`app/services/summarization.py`, `app/services/llm.py`, `app/services/podcast.py`, `app/services/decision.py`, `Dockerfile`, `.dockerignore`, `build.sh`, `auto_update_ytdlp.sh`, `setup_chrome_container.sh`)**：移除破壞 `#標籤` 與程式碼的 `\#` 跳脫並攔截只有標題無內文的異常輸出；合併 `GROQ_API_KEY` 與 `GROQ_FALLBACK_KEYS` 供 ASR 與 LLM 備援使用且遮罩重試與最終失敗日誌之金鑰；強化 Office ZIP 文件（`.docx/.pptx/.xlsx/.epub`）辨識與拒絕二進位亂碼降級；收緊 Podcast 網域檢查、支援 Apple Podcast `?i=` 指定單集、拒絕 Pocket Casts 指定 UUID 遺失時錯用首集與 RSS 音訊過濾順序；為 `decision.py` 加入 24h TTL、`hash:` 優先鍵與 `Choice` 結構驗證；修正 `auto_update_ytdlp.sh` `"none"` 崩潰、`build.sh` 啟動驗證與 `PUSH_IMAGES=1` 控管、`.dockerignore` 排除 `data/*.pkl`、`Dockerfile` 動態 `API_PORT` 健康檢查及 `example.env` / `README.md` / `SKILL.md` / `changelog.md` 同步更新。
  - 修復 `SHOW_PROCESSING=0` 時 `/start`、`/help`、`/lang`、`/clear`、`/context`、`/adfilter`、`/model`、`/boa`、`/tarot`、`/yiyu` 因 `processing_message` 為 `None` 觸發 `AttributeError` 崩潰。
  - 修復 `audio_transcription()` 區域變數 `chunk_size = 100 * 1000` 遮蔽全域 `CHUNK_SIZE` 的 Bug。
  - 修復 `/yt2text` 與 `/yt2audio` 繞過 `ALLOWED_USERS` 白名單及 `/yt2text` 錯誤比對過期導致錯誤訊息被包成 `transcript.txt` 的問題。
  - 修復 `is_safe_url()` DNS 解析失敗 Fail-Open 與漏檢 `not ip.is_global` / `host.docker.internal` 的 SSRF 漏洞，並補齊 `upload_url_to_box`、`get_web_title`、`extract_video_transcript` 及 `app/services/wiki.py` 路徑穿越與 JSON 解析防護。
  - 修復一般長對話 (`len >= 1000`) 誤自動公開發布至 David888 Wiki、圖片上傳被當純文字摘要、`handle('boa')` 與 `set_my_commands()` 阻塞非同步事件迴圈、`.cache/ad_decisions.json` 無鎖覆寫、`413` 截斷切掉 `--- END SOURCE CONTENT ---` 邊界、`/help` 漏列 `/adfilter` 與誤列 `六角` 牌陣、HTML 郵件未跳脫及 `setup_chrome_container.sh` 未映射 `3000/5900` Port 等問題。
  - 同步更新 `README.md`（修正未閉合圍欄、無效 `file://` 連結、環境變數表格）、`SKILL.md`、`example.env` 與 `docs/changelog.md`（補齊 `[2026-09-08]` 與 `[2026-08-28]` 遺漏標題）。

## [2026-11-19] - URL User Note (`[ DAVID888 筆記／觀點備註 ]`) & LLM Dedicated Response Section

### ✨ Added & Hardened
- **📝 URL 附帶個人筆記／觀點備註解析與結構安全淨化 (`app/services/content.py`)**:
  - 新增 `DEFAULT_AUTHOR_NOTE_LABEL`（`[ DAVID888 筆記／觀點備註 ]`）與 `get_author_note_label()`（支援透過環境變數 `AUTHOR_NOTE_LABEL` 自訂標題並經 `sanitize_raw_title(..., max_length=60)` 淨化控制字元與換行）。
  - 新增純線性 O(n) `parse_url_and_user_note(text, max_note_chars=4000)`：智慧拆解「URL + 個人觀點／筆記／疑問」（支援 URL 在前或觀點在後，包含緊貼中文文字與大寫 `HTTPS://`／`WWW.` scheme/host 正規化），採單次索引修剪尾端標點與外層對稱括號/引號（無 ReDoS / O(n²) 回溯，保護 Wikipedia 括號網址與 IPv6 `[::1]`、加上 token 前界排除 Email/`file:///www.`/`javascript:`），保留「讚」「推」等單字有效筆記，並提前執行長文長度守衛（URL 非位於開頭且剩餘字元 `> 600` 時直接回傳 `(None, None)`）。
  - 新增 `format_user_note_block(user_note, note_label=None, escape_markdown_structure=True)`（將原話以 `> ` blockquote 呈現、跳脫 `<`/`>` HTML 標籤字元並降級/跳脫 `#` 標題與 `---`/`===` 分隔線，確保 Wiki 永遠維持唯一首行 H1 且 Email/Telegram 無裸 HTML 注入）與 `escape_prompt_boundaries()`（中和偽造的 `--- BEGIN/END USER NOTE / SOURCE CONTENT ---` 邊界標記）；同步更新 `compose_summary_with_source()`、`prepare_wiki_content()` 與 `is_conversation_followup()`。
- **🤖 LLM 專屬回應段落、SSRF 前置守衛與全流程整合 (`app/legacy.py`, `main.py`, `app/services/quick_reply.py`)**:
  - `summarize()` 新增 `user_note=None` 參數並套用 `escape_prompt_boundaries()` 隔離筆記與來源文本，要求 LLM 於 `TITLE:` 後、`### ⓵` 前生成 `### 💬 【針對筆記與疑問回應】`（英文版 `### 💬 【Response to Your Note & Questions】`）。
  - `process_user_input()` 與 `is_url()` 統一支援大小寫不敏感 `https?://`，並於所有媒體探測（Pocket Casts / SoundOn / Apple Podcast / `yt-dlp` / 網頁抓取）**之前**強制執行 SSRF `is_safe_url()` 驗證。
  - Clef 廣告強制查看 (`show_ad:`) 改為每次提交獨立產生 `uuid` token（避免同 URL 不同筆記互相覆蓋），`build_quick_reply_source()` 將使用者筆記配額限制於 `min(600, max_chars // 4)`（標題改為 `使用者筆記與觀點：`）並套用 `escape_prompt_boundaries()`，同步整合 3 處 David888 Wiki 發布、MongoDB `summary_data` 與 `/help`。
- **🌐 FastAPI `/api/v1/summarize` 支援 `user_note` 與非同步邊界 (`app/api.py`, `api.py`)**:
  - `SummarizeRequest` 新增選用欄位 `user_note`（`max_length=4000`），`api_summarize` 透過 `await run_blocking(parse_url_and_user_note, user_input)` 拆出內聯筆記，並以 4000 字元總預算合併顯式 `user_note`（優先保留顯式筆記最多 3000 字＋內聯筆記剩餘預算），於回傳 `summary` 最上方附加淨化後的 `format_user_note_block()`。
- **🧪 新增完整效能、安全性與功能回歸測試 (`tests/test_content.py`, `tests/test_quick_reply.py`, `tests/test_api_keys.py`, `tests/test_security_audit.py`, `example.env`)**:
  - 覆蓋 4096 空白與 50,000 個 `)` ReDoS 防護（< 0.2s）、緊貼中文 URL、大寫 scheme/host、IPv6、單字筆記、Wiki/HTML/HR 結構淨化、Prompt 邊界防偽、Quick Reply 配額保護、Telegram/API 觀點+內網 URL 前置 SSRF 阻斷，以及顯式+內聯 `user_note` 合併規則。

## [2026-11-19] - Telegram /apikey Single-Key Management & Python 3.14 Upgrade

### ✨ Added
- **🔑 個人 Web API Key 管理服務 (`app/services/api_keys.py`)**：
  - 新增 `APIKeyManager` 與 `get_api_key_manager()` / `verify_user_api_key()`，每位 `(bot_scope, telegram_id)` 用戶嚴格限制僅能存在 **1 把有效金鑰**（`oli_` 前綴 + `secrets.token_urlsafe(32)`）。
  - 採確定性 MongoDB 主鍵 `"_id": f"{bot_scope}:{tg_id}"` 與 SHA-256 雜湊 (`hash_api_key`) 儲存、`hmac.compare_digest` 常數時間驗證，絕不落盤明文金鑰；重複建立直接原子 `insert_one` 並轉拋 `KeyAlreadyExistsError`；`rotate_key()` 採 `upsert=False` 原子覆寫（目標不存在或已撤銷時拋 `KeyNotFoundError` 防止復活），並徹底移除正向憑證快取，每次 `verify_key_owner()` 即時向權威儲存查核（同時檢查 `is_telegram_user_allowed()`，自 `ALLOWED_USERS` 移除成員立即 401 失效）。
  - 新增 `get_bot_scope()`（取 `TELEGRAM_TOKEN` 前 12 碼 SHA-256 雜湊，未設定時記 warning 並回傳 `default`），確保 `@oli_summary_bot` 與 `@quantaar_bot` 共用同一 MongoDB (`bot_database.api_keys`) 時嚴格跨環境隔離；無 MongoDB 時支援跨行程 `fcntl.flock` 鎖定與原子寫入 JSON (`API_KEYS_FILE`) 或執行緒安全記憶體儲存（JSON 損毀時記 error 並拋 `RuntimeError`，絕不靜默清空覆寫）。
  - 新增 4 層智慧 API Base URL 自動偵測 (`resolve_api_base_url`, `record_observed_base_url`, `detect_public_ip`, `get_trusted_hosts`, `is_proxy_headers_trusted`)：依序優先採用 `API_PUBLIC_URL`（嚴格拒絕 userinfo、query、fragment 與引號）$\rightarrow$ 僅於設定 `API_TRUSTED_HOSTS` 且於認證通過後才記錄之受信任外部 Host（預設停用動態 Host 學習，並依 `API_TRUST_PROXY_HEADERS` 決定是否採信 `X-Forwarded-*`，徹底杜絕 Host Header Poisoning）$\rightarrow$ 公網 IP 探測（成功 1 小時 / 失敗 60 秒快取 + `_parse_safe_port` 安全解析 `API_PORT`）$\rightarrow$ `localhost:API_PORT`。
  - 新增 `build_curl_usage_guide()` 使用 `shlex.quote` 安全保護 URL 與 Authorization Header，產出可複製執行的 `/health`、網址/YouTube 摘要與純文字摘要 cURL 指令及 HTTP 安全提醒。
- **🤖 Telegram `/apikey` 指令與安全互動選單 (`app/legacy.py`, `main.py`)**：
  - 新增 `/apikey` 指令、`set_my_commands` 註冊與 `/help` 說明，僅限私訊 (`chat.type == 'private'`) 使用，群組呼叫自動攔截保護金鑰不外洩。
  - 所有管理與儲存呼叫皆透過 `await run_blocking(...)` 執行，實作 `apikey:create`、`apikey:rotate_confirm`、`apikey:rotate_exec`（含 `KeyNotFoundError` 友善引導）、`apikey:revoke_confirm`、`apikey:revoke_exec`、`apikey:curl` 與 `apikey:cancel` 按鈕流程（使用 `html.escape` 搭配 `<pre><code>` 安全排版）。
  - 於 `handle_button_click` 最開頭補齊 `ALLOWED_USERS` 白名單驗證守衛。
- **🌐 FastAPI 雙軌 Token 驗證與可信任 Host 觀測 (`app/api.py`, `api.py`)**：
  - 移除未認證 middleware 對動態 Host 的無條件寫入；改於 `verify_token` 通過靜態或動態驗證後，始呼叫 `_record_trusted_request_host(request)`。
  - 靜態 token 使用 UTF-8 bytes `secrets.compare_digest` 比對避免非 ASCII 例外；動態 token 先經 `is_candidate_dynamic_api_key` 快篩再透過 `run_blocking(verify_user_api_key, token)` 驗證，後端異常時回傳 HTTP `503 Service Unavailable`。
- **🧪 新增完整單元與安全回歸測試 (`tests/test_api_keys.py`, `tests/test_dockerfile.py`)**：
  - 覆蓋 `bot_scope` 跨環境隔離、確定性 `_id` 單一金鑰限制與 `KeyNotFoundError` 防復活契約、並發多執行緒 Rotate/Revoke 零快取即時失效、`ALLOWED_USERS` 即時撤權、`API_TRUSTED_HOSTS` / `API_TRUST_PROXY_HEADERS` 防 Host Header Poisoning、損毀 JSON 拒絕覆寫、`API_PORT` / `API_PUBLIC_URL` 驗證、非 `oli_` 與非 ASCII 401 / DB 異常 503，以及 Python 3.14 Dockerfile 與 `audioop-lts` 檢查。

### 🔄 Changed & Improved
- **🐍 基礎映像全面升級至 Python 3.14 (`Dockerfile`, `AGENTS.md`, `example.env`, `README.md`)**：
  - `Dockerfile` 基礎映像由 `python:3.12-slim` 升級至 `python:3.14-slim`（搭配 `requirements.txt` 之 `audioop-lts; python_version >= '3.13'` 相容套件）。
  - `example.env`、`README.md` 與 `AGENTS.md` 同步補齊選用環境變數 `API_PUBLIC_URL` 與 Python 3.14 部署規格說明。

## [2026-11-19] - LLM SEO Title Generation & Viral Social Post Overhaul

### ✨ Added
- **🏷️ 單次 LLM 整合產出「專業知識＋好奇心反差」SEO 標題 (`app/services/content.py`, `app/legacy.py`, `main.py`, `app/api.py`, `api.py`)**:
  - 於 `SYSTEM_PROMPT_ZH` 與 `SYSTEM_PROMPT_EN` 開頭規範 LLM 在回覆第一行輸出 `TITLE: ...`，以零額外 API 呼叫成本同時產出部落格 SEO 標題與結構化摘要（強制改寫簡體/外文/平庸原標題為自然道地的台灣繁體中文或英文）。
  - 於 `app/services/content.py` 新增 `sanitize_raw_title`、`is_valid_raw_title`、`is_summary_error_message`、`extract_title_from_summary`（嚴格僅檢查第一個非空行、淨化成對粗斜體與引號、並於無效標題行時自動剝除避免外洩）、`resolve_final_title`、`compose_summary_with_source` 與 `prepare_wiki_content`（保留原有 `needs_title_localization` 與 `localize_title` 共用佔位清單 `_INVALID_RAW_TITLES`）。
  - 主標題完全取代原始標題，不再附加 `(Original Title)` 括號；若存在有效且不同的原始標題，統一於文章底部來源連結上方呈現 `🏷️ 原始標題：{raw_title}`；Email 主旨同步經 `sanitize_raw_title` 淨化防止換行標頭異常。
  - `summarize()` 新增 `raw_title` 與 `return_title` 選用參數（先解析標題行再進行 `#` Hashtag 跳脫）；`get_video_title()` 與 `get_web_title()` 新增 `localize` 開關避免重複呼叫 LLM；`resolve_final_title()` 一致整合所有摘要進入點（一般訊息、廣告強制查看 `show_ad:`、文件上傳 `handle('file')`、FastAPI `/api/v1/summarize` 含 `is_ad` 隱藏分支）。
  - `SummarizeResponse` (`app/api.py`, `api.py`) 新增選用欄位 `original_title`，並於 `api_summarize` 改用 `await run_blocking(is_safe_url, user_input)` 避免同步 DNS 解析阻塞事件迴圈。
- **🧩 抽出 Telegram HTML 安全分片與遞送服務 (`app/services/telegram_delivery.py`)**:
  - 新增 `_split_markdown_safely(text, limit=3200)`（於段落/換行/句點/空白邊界安全切分原始 Markdown）。
  - 重構 `format_for_telegram`：先轉換 `<strong>`/`<em>` 為 `<b>`/`<i>`、以 `decode_contents()` 保留段落與清單內的行內樣式、移除破壞實體的 `html.unescape()` 以安全渲染 `a < b` / `Vec<T>` / `<script>`，並嚴格 unwrap 非 Telegram 支援的 HTML 標籤（僅保留 `b, i, u, s, a, code, pre, tg-spoiler`）。
  - 重構 `send_telegram_formatted`：以 `run_blocking` 在背景執行緒格式化每塊分片，**單塊 HTML 失敗或超限時僅針對該塊降級純文字發送**，絕不重複發送先前已成功送達的前段訊息。
- **📚 David888 Wiki 頁首保護與來源資訊一致化 (`app/services/content.py`, `app/legacy.py`, `main.py`)**:
  - `prepare_wiki_content()` 自動將摘要內文中的 `# ` 降級為 `## `（避免 `sanitize_wiki_markdown` 誤刪一級標題前的摘要段落），以 `# {clean_title}` 作為唯一首行 H1 標題，並於文末附上原始標題與來源連結。

### 🔄 Changed & Improved
- **📱 重構「社群貼文風」為單篇高互動純文字爆文版 (`app/services/quick_reply.py`)**:
  - 重寫 `build_transform_prompt("social", ...)`，改為產出單篇 **220～320 字（嚴格 < 400 字元）**（英文版 **55-85 words / < 450 字元**）、具備個人觀點與適度犀利吐槽、強反差 Hook 開頭且**零 Markdown** 的高互動貼文，並於所有轉換 Prompt 加入 `--- BEGIN SOURCE CONTENT ---` 資料邊界保護。
  - 強化 `clean_social_post_output(text, max_chars=480)`：清除程式碼圍欄、`###` 標題、`>` 引用、清單符號、`**/__/*/~~/\`` 與 Markdown 連結，收緊標籤前綴正則以保留自然口語「重點：」「標題：」，並內建 480 字元優雅句末截斷保護。
- **🎛️ 修復全系列 Quick Reply 素材來源與 LLM 失敗攔截 (`app/services/quick_reply.py`, `app/legacy.py`, `main.py`, `app/api.py`, `api.py`)**:
  - 優化 `build_quick_reply_source()`：僅剝除結尾固定 bot 宣傳語，並於摘要過短時依剩餘字元預算逐段累積原文。
  - 所有摘要進入點以 `is_summary_error_message()` 攔截失敗或空回應，絕不寫入 MongoDB、寄送 Email、推送 Discord 或覆寫對話歷史（FastAPI 端點改回 HTTP 503）；Quick Reply 亦攔截空回應避免覆蓋歷史與發送空訊息。
- **🧪 補充完整單元測試 (`tests/test_content.py`, `tests/test_quick_reply.py`, `tests/test_telegram_delivery.py`)**:
  - 新增分片、錯誤訊息攔截、標題淨化、第一行嚴謹提取、Wiki 頁首降級、社群輸出清理與長度上限、及模擬分塊局部失敗不重送的完整測試。

## [2026-11-17] - Upstream Dependency Upgrades & Cleanup

### 🔄 Changed & Improved
- **📦 升級並精簡核心上游套件 (`requirements.txt`)**:
  - 升級 `python-telegram-bot` (`21.1.1` $\rightarrow$ `>=22.8`)，支援最新 Telegram Bot API 10.0 與現代非同步特性。
  - 升級 `trafilatura` (`1.9.0` $\rightarrow$ `>=2.3.1`)，取得最新網頁正文提取修正與改進。
  - 升級 `firecrawl-anydoc` 最低版本需求為 `>=0.2.4`，並於 `app/services/content.py` 的 `convert_document_to_markdown` 明確捕捉 `NeedsOcrError`，對純掃描影像 PDF 回傳友善提示（避免誤將二進位 PDF 內容送入摘要流程）。
  - 明確補列直接依賴 `requests>=2.34.2` 與 `pydantic`。
  - 移除過時或未於主程式使用的套件：`asyncio==3.4.3`（Python 3.4+ 已內建標準庫）、`youtube_transcript_api==0.6.2`、`litellm` 與 `openai`（並同步移除 `app/legacy.py`、`main.py` 未使用的 `from openai import OpenAI` 匯入），縮減 Docker 映像體積與建置時間。
- **🐳 更新建置與自動化更新腳本 (`Dockerfile`, `auto_update_ytdlp.sh`)**:
  - `Dockerfile` 改用官方現行 Deno 安裝腳本網址 (`https://deno.land/install.sh`)。
  - `auto_update_ytdlp.sh` 改用 `packaging.version.Version`（並保留 `pkg_resources` 回退相容），避免新版 `setuptools` 移除 `pkg_resources` 導致版本比對失敗。
- **🧪 補充單元測試 (`tests/test_content.py`)**:
  - 新增 `test_convert_document_to_markdown_needs_ocr_pdf` 驗證掃描影像 PDF 的 `NeedsOcrError` 友善錯誤處理。

## [2026-11-08] - YouTube Multi-Language Audio Track Selection, Subtitle Priority & AI Title Localization

### ✨ Added
- **🌐 多國語言 YouTube 影片繁中音軌優先選擇 (`app/legacy.py`, `main.py`)**:
  - 針對 YouTube 多國語言配音影片（如跨國頻道多音軌支援），重構 yt-dlp 格式選擇器：
    `bestaudio[language=zh-Hant]/bestaudio[language=zh-TW]/bestaudio[language=zh-HK]/bestaudio[language=zh]/bestaudio[language=zh-Hans]/bestaudio[language=zh-CN]/bestaudio[language=en]/bestaudio[protocol^=http]/bestaudio/best`
  - 自動依序優先下載繁體中文 (`zh-Hant`, `zh-TW`, `zh-HK`)、中文 (`zh`, `zh-Hans`, `zh-CN`)、英文 (`en`) 音軌，徹底解決過往預設抓取原始外語音軌（如西班牙語、法語）導致 Whisper 語音轉文字與摘要語言錯亂的問題。
  - 同步套用於語音聽寫 (`audio_transcription`) 與音訊下載指令 (`/yt2audio`)。

- **🎯 中文字幕選取優先級重構 (`extract_video_transcript`)**:
  - 原先字幕語言順序將 `en` 置於首位，導致包含雙語字幕之影片預設抓取英文字幕。
  - 重構優先順序為 `['zh-Hant', 'zh-TW', 'zh-HK', 'zh-Hans', 'zh-CN', 'zh', 'en']`，繁體中文字幕最優先提取，並於下載後自動清理同影片之其餘語言暫存字幕檔，避免磁碟空間浪費。

- **🏷️ 外語影片與網頁標題 AI 繁體在地化翻譯 (`app/services/content.py`)**:
  - 新增 `needs_title_localization(title)` 與 `localize_title(title)` 服務模組。
  - 智慧偵測標題語言特徵：若非中文標題（如西班牙文、英文、日文假名、韓文等），自動調用 LLM 進行自然流暢的繁體中文（台灣）在地化翻譯。
  - 標題自動呈現格式為：`{繁中在地化標題} ({原始外語標題})`（例如：`誰是史上最有錢的人？ (¿Quién ha sido el más RICO de la historia?)`）。
  - 自動貫穿應用至 Telegram 摘要推播標題、David888 Wiki 知識庫發布頁面主標題與電子郵件主旨，徹底杜絕外語頻道發布至 David888 Wiki 時出現生硬外文標題的問題。
  - 已具備中文字元之標題與系統通用標題直接略過，零 Token 消耗、零延遲。

- **🧪 單元測試覆蓋 (`tests/test_content.py`)**:
  - 新增外語標題在地化偵測、中文標題快速略過、外文標題繁中翻譯格式化及 LLM 異常降級回退等完整測試用例。

## [2026-11-08] - Magpie Gateway Integration with Automatic Multi-Tier Fallback

### ✨ Added
- **🦜 支援自建 Magpie Gateway 作為優先主要推論端點 (`app/services/llm.py`)**:
  - 新增環境變數 `MAGPIE_API_KEY`、`MAGPIE_BASE_URL` 與 `MAGPIE_MODEL` 第一類原生支援。
  - 當設定 `MAGPIE_API_KEY` 時，系統自動將 Magpie 端點掛載為 **Tier 0 (主要推論引擎)**，預設模型為 `auto/gemini-3.8-flash`（支援深度思考推理與高品質結構化繁中輸出）。
  - **平滑備援機制 (Automated Multi-Tier Fallback)**：
    - 原先配置的 `LLM_API_KEY`（如 Google Gemini 原廠 API）與 `LLM2_API_KEY`（如 Groq Llama/GPT-OSS）自動無縫轉為 Tier 1、Tier 2 降級備援候選池。
    - 當 Magpie Gateway 遭遇網路逾時、配額滿載或伺服器異常時，自動透明切換至原廠備援模型，保證 Telegram Bot 服務 100% 不中斷。
  - **Magpie 內部同節點模型容錯 (Intra-Provider Alias Retry)**：
    - 在調用 Magpie 遭遇 400/404/413 錯誤時，自動在 Magpie 節點內部循序重試備用模型（`auto/gemini-3.8-flash` $\rightarrow$ `group/agy-first` $\rightarrow$ `auto/gemini-3.5-flash-lite` $\rightarrow$ `antigravity/gemini-3.8-flash`），最大化推論成功率。
- **🧪 完整單元測試覆蓋 (`tests/test_llm.py`)**:
  - 新增 Magpie 主要端點自動偵測、Magpie 異常平滑切換至備援 LLM、Magpie 同節點模型別名重試測試，全數通過。

## [2026-10-29] - Restore Automated CD Pipeline & Deploy Dedicated Scoped Watchtower

### 🔧 Fixed & Improved
- **🔄 全面修復私有伺服器 (`git.glsoft.ai`) 之自動持續部署 (CD) 機制**:
  - **斷線根本原因分析**：
    - 私有主機 `git.glsoft.ai` 原先的全域 `watchtower` 容器於 2026-09-22 因主機上新增其它 scoped watchtower 實例引發衝突而停止運行。
    - 缺少專屬的 summary 監控實例，且舊版容器未設定 Watchtower scope 標籤與遠端映像檔命名空間 (`tbdavid2019/`)，導致 Docker Hub pull 失敗，使 `@oli_summary_bot` 自動更新中斷達 5 週。
  - **部署專屬 `watchtower-summary` 容器**：
    - 在 `git.glsoft.ai` 部署獨立容器 `watchtower-summary`，配置 `--scope summary --label-enable`、`WATCHTOWER_POLL_INTERVAL=60`、`DOCKER_API_VERSION=1.44`。
    - 清理 5 週前遺留之失效全域 watchtower 實例。
  - **標準化容器標籤與啟動腳本 (`build.sh`)**：
    - 更新 `build.sh`，容器啟動參數強制帶入 `--label com.centurylinklabs.watchtower.enable=true` 與 `--label com.centurylinklabs.watchtower.scope=summary`，並指名官方 Registry 映像檔 `tbdavid2019/telegram-bot-summary:latest`。
    - 實機日誌驗證確認 `watchtower-summary` 每 60 秒定期輪詢 Docker Hub，狀態回傳 `Failed=0 Scanned=1 Updated=0` 正常巡檢。
- **📖 更新架構與部署文檔 (`AGENTS.md`, `README.md`)**:
  - 精確記錄雙主機之 Watchtower 運作拓撲（`aicreate360.com` 全域監控 vs `git.glsoft.ai` 獨立 Scoped 監控）。


## [2026-10-28] - Clef-Flash System One Intelligent Ad & Spam Decision Filter

### ✨ Added
- **🛡️ 自建 Clef-Flash System One 智慧廣告與垃圾訊息決策模型過濾 (`app/services/decision.py`)**:
  - 整合自建 Clef-Flash System One 決策推論引擎（極速推論 <200ms、免外部 Token 費用），自動判定文本與網頁內容是否屬於商業行銷、詐騙引流或推廣廣告。
  - **雙節點高可用容錯 (Dual-Node Failover)**：
    - **主要節點 (Primary)**：`https://clef.create360.ai/v1/systemone`
    - **備援節點 (Fallback 2)**：`https://clef.aiurl.tw/v1/systemone`
  - **預設開啟與超時保護**：
    - 決策過濾預設開啟 (`DECISION_AD_FILTER_ENABLED=true`)。
    - 決策推論超時設為 30 秒 (`CLEF_TIMEOUT_SECONDS=30`)。
    - **平滑降級機制 (Graceful Fallback)**：當主節點與備援節點皆失效或逾時，日誌記錄警告並自動作為正常內容放行，確保核心摘要功能 100% 不中斷。
  - **三層式高效快取架構 (Multi-Tier Caching)**：
    - 前人讀取過的內容（依據文字 SHA-256 與正規化 URL）立即儲存決策結果。
    - 依序查驗：In-Memory 快取（執行緒鎖防競爭）$\rightarrow$ MongoDB 永久集合 (`bot_database.ad_decisions`) $\rightarrow$ 本地磁碟快取 (`.cache/ad_decisions.json`)。後續相同網址或文本直接命中快取，完全省去重複推論與 Token 消耗。
- **📱 Telegram 廣告隱藏與強制查看摘要機制 (`app/legacy.py`, `main.py`)**:
  - 當內容經判定為廣告時，自動攔截並隱藏摘要輸出，回傳防護提示訊息。
  - 附帶 `[👁️ 仍要查看摘要]` 互動按鈕，若使用者確實需要總結廣告內容，點擊即可直接依快取內容強制產出摘要，不需重新上傳。
  - 新增 `/adfilter` 機器人命令與 `set_adfilter:<on|off>` 按鈕，允許使用者查詢狀態或自由切換過濾開關。
- **🌐 FastAPI 端點同步支援廣告過濾 (`app/api.py`, `api.py`)**:
  - `SummarizeResponse` 新增 `is_ad: bool` 標籤。
  - 於調用 LLM 前優先執行決策過濾，若判定為廣告則回傳 `status="hidden"` 與 `is_ad=True`，防止不必要的 Token 消耗。
- **🧪 完整單元測試覆蓋 (`tests/test_decision.py`)**:
  - 涵蓋主節點推論成功、主節點故障平滑切換備援節點、雙節點皆掛掉降級容錯、In-Memory / URL / Disk / MongoDB 快取命中以及 FastAPI 廣告攔截，99/99 測試全數通過。

## [2026-10-28] - Fix Dependabot Python-Markdown CVE & Support Pocket Casts (pca.st) Podcasts

### 🔧 Fixed
- **🛡️ Dependabot CVE-2025-69534 / GHSA-5wmx-573v-2qwq 安全漏洞修復 (`requirements.txt`)**:
  - 將 `markdown==3.7` 升級為 `markdown>=3.8.1`，修復惡意 HTML 標記序列導致 `html.parser.HTMLParser` 拋出未捕捉 AssertionError 造成拒絕服務 (DoS) 的安全漏洞。

### ✨ Added
- **🎙️ Pocket Casts 與 pca.st 短網址深度整合支援 (`app/services/podcast.py`)**:
  - 新增 `app/services/podcast.py` 獨立模組：
    - `is_pocketcasts_url(url)`：支援 `pca.st`、`pocketcasts.com`、`play.pocketcasts.com` 及其各子網域。
    - `resolve_pocketcasts_url(url)`：自動解析 Pocket Casts 官方短網址 `https://pca.st/<code>`，透過 HTTP 重定向與現代瀏覽器 User-Agent 取得標準 Podcast 頁面網址。
    - `extract_pocketcasts_episode(url)`：解析 Podcast UUID 與 Episode UUID，直接對接 Pocket Casts 官方 API (`podcast-api.pocketcasts.com/podcast/full/{uuid}`)，精準鎖定用戶指定的單集音訊（或預設最新一集），直接取得 CDN MP3 串流網址、標題與長度，並透過 `@lru_cache` 實現記憶體快取。
    - `get_pocketcasts_title(url)`：提供格式化之集數與節目名稱（例如 `EP718 你在「財富階梯」的哪一階？你想上升到哪一階？你打算怎麼做？ - 大人的Small Talk`）。
- **🧪 完整單元測試覆蓋 (`tests/test_podcast.py`)**:
  - 涵蓋 URL 格式驗證、短網址重定向解析、特定單集與最新單集抓取、API 容錯與 SSRF 防護、快取命中以及與 `process_pocketcasts_url`、`get_web_title` 之整合測試，全數通過 (90/90 測試)。

### 🔄 Changed & Improved
- **🔀 雙進入點同步優化 (`app/legacy.py`, `main.py`)**:
  - 更新 `process_pocketcasts_url`：由原先僅能抓取 RSS 第一集最新單集，升級為可精準下載用戶指定的 Pocket Casts 單集音訊並進行 Whisper 轉錄。
  - 更新 `get_web_title`：支援 Pocket Casts 網址直接呈現真實節目與單集標題，避免原先網頁抓取被 CloudFront/AWS WAF 阻擋回傳「無法下載該網頁的內容。」之異常。
  - 更新音訊下載串流請求，附加現代瀏覽器 User-Agent 標頭以防止音訊伺服器擋爬蟲。

## [2026-09-24] - GitHub Container Registry (GHCR) Dual-Publishing Support

### ✨ Added
- **📦 GitHub Container Registry (GHCR) 雙註冊中心發布支援**:
  - 更新 `.github/workflows/docker-build.yml`：
    - 加入 `permissions: contents: read, packages: write` 賦予 GITHUB_TOKEN 容器寫入權限。
    - 新增 GHCR 自動登入步驟 (`docker/login-action@v3` via `ghcr.io`)。
    - 在 `docker/metadata-action@v5` 配置雙 Image 標籤：同步發布至 `tbdavid2019/telegram-bot-summary` (Docker Hub) 與 `ghcr.io/tbdavid2019/telegram-bot-summary` (GitHub Packages)。
  - 更新 `build.sh`：本地部署腳本亦同步追加 `ghcr.io/tbdavid2019/telegram-bot-summary:latest` 標籤與容錯推送。
  - 更新 `README.md`：補充從 GHCR (`ghcr.io/tbdavid2019/telegram-bot-summary:latest`) 拉取與更新容器之指令說明。
- **🧪 測試與環境相容性強化 (`tests/test_content.py`)**:
  - `test_detect_file_type_markdown` 增加對本地未安裝 `magika` 輕量環境回傳 `md` 標籤之向下相容斷言。

## [2026-09-08] - Google Magika AI File Detection & Local Audio ASR

### ✨ Added
- **🧠 Google Magika 深度學習檔案內容類型識別 (`app/services/content.py`)**:
  - 整合 Google 開源之 `magika`（100+ 種檔案類型，精確率 >99%），以輕量 CNN ONNX 模型進行純本地 CPU 毫秒級推論（單檔 1~5ms，RAM ~30MB）。
  - 新增 `detect_file_type(file_path)`：回傳規範化之 `label`、`mime_type`、`group`（`document`, `audio`, `video`, `code`, `text`, `archive`, `executable` 等）、`description`、`extensions`、`is_text` 與信心分數 `score`。
  - 支援單例模式惰性初始化 (`get_magika()`)，並於 Magika 不可用或未安裝時平滑降級至副檔名/MIME 猜測，保證 100% 執行期韌性。
- **🎧 本地音訊檔案轉錄支援 (`transcribe_local_audio`)**:
  - 新增 `transcribe_local_audio(file_path)`：當使用者以文件或音訊形式上傳錄音/音檔（`.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.aac`, `.opus`）時，透過 `pydub` 分塊並調用 Groq Whisper API (`whisper-large-v3`, `response_format=verbose_json`)，自動生成精準時間戳記逐字稿。
  - 長文本遵循 Telegram 防刷屏與 4,096 字元限制規範，當逐字稿大於 1,000 字元時自動以 `.txt` 檔案發送，並接著由 LLM 產出結構化重點摘要。
- **🐳 Dockerfile 模型預載入與離線鏡像構建驗證**:
  - 在 `Dockerfile` 中加入 `RUN python3 -c "from magika import Magika; m = Magika(); print('Magika initialized successfully')"`，將 Magika 模型權重在 Build 階段固化於容器 Image Layer 內，容器執行期 100% 零聯網離線推論。

### 🔄 Changed & Improved
- **🔀 Telegram 文件處理智慧分流路由 (`app/legacy.py`, `main.py`)**:
  - 徹底重構 `handle_file`：下載暫存檔後第一時間經由 Magika 判斷真實內容類別：
    - **音訊類 (`group == "audio"`)**：分流至 Whisper ASR 轉錄並輸出逐字稿與摘要。
    - **壓縮檔/執行檔類 (`group in ("archive", "executable")`)**：友善提示使用者檔案類型不支援，防止程式錯誤崩潰。
    - **純文字/程式碼 (`is_text` 或 `group in ("text", "code")`)**：直接以 UTF-8 讀取加速處理。
    - **文檔類 (`group == "document"`)**：如遇無副檔名或副檔名缺失之文件，自動根據 Magika 推薦之標準副檔名建立格式提示，讓 `firecrawl-anydoc` 順利完成 Markdown 轉檔。
- **🧪 完整單元測試覆蓋 (`tests/test_content.py`, `tests/test_dockerfile.py`)**:
  - 新增針對純文字、Markdown、降級容錯、不支援壓縮檔拋出例外、Whisper 音訊轉錄 mock 以及 Dockerfile/requirements.txt 內建檢查之單元測試，全數通過 (77/77 測試)。

## [2026-09-03] - Fix LLM Empty Summary Delivery, Groq Fallback 413 Truncation & Model Catalog Update

### 🔧 Fixed
- **🚨 阻絕空摘要與僅傳送頁尾之錯誤傳遞 (Empty Summary Delivery Fix)**:
  - 修復 `summarize()` (`app/legacy.py`, `main.py`, `app/services/summarization.py`) 在所有備援 LLM 端點皆故障或返回空字串時，仍將機器人宣傳頁尾直接附加並送出的問題。
  - 現在當 `call_gpt_api` 返回空字串時，系統會明確回傳 `⚠️ 摘要生成失敗：所有 AI 模型服務暫時無法回應或連線超時，請稍後再試或通知管理員。`，並於日誌輸出 `[ERROR]`。
- **💥 Groq 備援 HTTP 413 Payload Too Large 自動截取降級修復 (`app/services/llm.py`)**:
  - 當 Gemini（支援 100 萬 token）處理長文本（如大型 YouTube 逐字稿）遭遇失效而降級至 Groq 時，因 Groq 免費級別有 8,000 TPM/請求長度限制導致 HTTP 413 錯誤。
  - 新增 413 智慧自適應降級截取機制：當收到 413 且文字長度大於 6,000 字元時，自動於尾部加入提示並保留安全容量內文本重新發送，使 Groq 能成功生成結構化摘要。
- **🤖 Groq 模型目錄過期與別名支援 (`app/services/llm.py`)**:
  - 將 Groq 預設自動降級模型與別名列表同步至 Groq 目前現行可用模型（`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`, `qwen/qwen3.6-27b`），避免因過期模型名（如 `llama-3.3-70b-versatile`）引發 HTTP 404/400 失敗。
- **🔄 Gemini 非官方模型名自動映射相容**:
  - 在 `_normalize_model_for_endpoint` 中將誤植之 `gemini-3*` 自動轉換相容為 `gemini-2.5-flash`，防止無效模型名稱直接導致 400 Bad Request。

## [2026-09-02] - Comprehensive 7-Layer Security Audit & Codebase Hardening

### ✨ Added
- **🛡️ 7 層安全防禦架構與 SSRF 防護 (`app/services/content.py`)**:
  - 新增 `is_safe_url()` 嚴格校驗傳入之 URL，阻絕所有私有內部網段 (RFC1918 `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)、本機迴路 (`127.0.0.0/8`, `localhost`)、雲端主機中繼資料服務 (`169.254.169.254`, `metadata.google.internal`, `metadata.aws`) 與非 HTTP(S) 通訊協定 (`file://`, `gopher://`, `dict://`)，徹底防堵 Server-Side Request Forgery (SSRF) 攻擊。
  - 在 `app/legacy.py`、`main.py` 與 `app/api.py` 的網頁解析 (`scrape_text_from_url`)、Podcast RSS 抓取 (`extract_rss_*`)、Podcast 音訊下載 (`download_and_transcribe_podcast`)、影片下載 (`download_video_audio`) 及 FastAPI 摘要端點 (`/api/v1/summarize`) 全面套用 SSRF 阻斷。
- **🌐 FastAPI 安全標頭中介軟體 (HTTP Security Headers Middleware)**:
  - 為 `app/api.py` 及 `api.py` 加入安全回應標頭中介層：
    - `X-Content-Type-Options: nosniff`（防範 MIME 嗅探攻擊）
    - `X-Frame-Options: DENY`（防範 Clickjacking 點擊劫持）
    - `Referrer-Policy: strict-origin-when-cross-origin`（保護使用者來源 URL 隱私）
    - `Permissions-Policy: camera=(), microphone=(), geolocation=()`（禁用敏感瀏覽器功能）
    - `X-XSS-Protection: 1; mode=block`
- **🧪 完整安全審計單元測試套件 (`tests/test_security_audit.py`)**:
  - 新增針對 SSRF 阻擋、FastAPI 安全標頭、常數時間 Bearer Token 驗證、Prompt Injection 提示詞隔離邊界以及 Settings 配置之端到端測試，全數通過 (69/69 測試)。

### 🔄 Changed & Improved
- **🧠 Prompt Injection 提示詞防禦與外部資料隔離**:
  - 在 `summarize` (`app/legacy.py`, `main.py`, `app/services/summarization.py`) 中，將所有外部不可信來源資料嚴格包裹於 `--- BEGIN SOURCE CONTENT ---` 與 `--- END SOURCE CONTENT ---` 結構化隔離標記中。
  - 於 System Prompt 中注入安全規範指令，要求 LLM 嚴格僅將標記內文本視為被動資料進行結構化摘要，嚴禁執行或受內部指令/提示詞覆蓋（Prompt Override）所引導。
- **🔒 常數時間 API 金鑰驗證 (Timing-Attack Safe Verification)**:
  - 在 `app/api.py` 與 `api.py` 的 `verify_token` 中改用 `secrets.compare_digest` 進行常數時間比對，徹底消除時序攻擊（Timing Attack）風險。
- **📦 FastAPI 請求載荷長度與記憶體耗盡防禦 (DoS Protection)**:
  - 在 `SummarizeRequest` 中為 `input` 設置最大長度約束 `max_length=1_000_000`（100 萬字元），並為 `language` 與 `model` 加入欄位長度上限，防禦惡意大型 Payload 造成記憶體耗盡。
- **🧹 暫存檔案生命週期與例外安全清理 (Try-Finally Temp File Cleanup)**:
  - 全面盤點並重構所有暫存音訊 (`.wav`, `.mp3`)、文字 (`.txt`) 及文件檔案處理邏輯（`handle_file`、`download_and_transcribe_podcast`、`audio_transcription`、`handle_yt2audio`、`handle_yt2text`），以 `try...finally:` 確保在遇到網路異常、API 錯誤或超時等非正常流程時，磁碟上的暫存檔必定 100% 刪除，避免磁碟耗盡 (Disk Exhaustion DoS)。
- **📁 檔案上傳路徑穿越與副檔名過濾 (Path Traversal Hardening)**:
  - 在 `handle_file` 中對文件名稱與副檔名以正則過濾 `re.sub(r'[^a-zA-Z0-9._-]', '', ext)`，並清洗 `file_id`，確保暫存路徑安全受限於 `/tmp/` 系統暫存區。

### 🔧 Fixed
- **🔑 `.gitignore` 憑證與機密檔案防護不全修復**:
  - 擴充 `.gitignore` 涵蓋 `.env.*`、`*.env`、`*.pem`、`*.key`、`*.pfx`、`*.crt`、`*.p12`、`*.cer`、`*.id_rsa`、`*.log`、`*.tmp`、`*.wav`、`*.mp3`、`*.mp4`、`downloads/` 等，阻絕任何金鑰或快取被意外提交至版控。
- **🔑 多金鑰池下的 Groq API 金鑰提取修復**:
  - 修復 `app/legacy.py` 與 `main.py` 在多金鑰模式下調用 Whisper ASR 時未拆分逗號可能傳入多組金鑰導致認證失敗的問題。
- **⏱️ Telegram 命令設置連線超時防護**:
  - 為 `clear_old_commands` 與 `set_my_commands` 的 `requests.post` 補上 `timeout=WEB_REQUEST_TIMEOUT_SECONDS`，防止啟動時 Telegram API 卡頓導致行程無限期掛起。
- **👥 `allowed_users` 白名單空白字元相容性修復**:
  - 解析 `ALLOWED_USERS` 時自動移除字串前後空白 (`[u.strip() for u in allowed_users.split(',') if u.strip()]`)。
- **🛡️ Chrome Headless 容器資料夾權限收緊**:
  - 將 `setup_chrome_container.sh` 中的 `chmod -R 777` 修正為 `chmod -R 700`，保護 Chrome Session Profile 與 Cookie 不被本機非授權帳號存取。

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
- **CI / GitHub Actions 支援 Node.js 24**:
  - 在 `.github/workflows/docker-build.yml` 中設定 `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true`，消除 GitHub Actions Node 20 棄用告警並升級至 Node 24 執行環境。
- **單元測試全覆蓋 (`tests/test_llm.py`)**:
  - 增加 9 項新測試，涵蓋端點探索、Groq 自動備援、Google Gemini 相容性轉譯、HTTP 4xx/5xx 容錯切換、多層級連續故障轉移及使用者自選模型優先權，全測試通過率 100% (62/62)。

## [2026-08-28] - Quick Reply Interactive Keyboard & Structured Summary Upgrade

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



## [2025-12-03] - LLM Model Switching, Book of Answers & Ad Skipping

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

## [2025-11-19] - Multi-Language Summary, Follow-up QA & Podcast Support

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
