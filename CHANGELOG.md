# Changelog

本專案變更紀錄以**日期**為主軸整理，不採用語意化版本號（詳細技術實作紀錄亦同步維護於 [docs/changelog.md](docs/changelog.md)）。

---

## 2026-11-19

### Added & Improved
- **URL 附帶 `[ DAVID888 筆記／觀點備註 ]` 與 AI 專屬回應段落 (`app/services/content.py`, `app/legacy.py`, `app/api.py`, `app/services/quick_reply.py`)**：新增純線性 O(n) `parse_url_and_user_note`、`format_user_note_block`、`escape_prompt_boundaries` 與 `get_author_note_label`（支援 `AUTHOR_NOTE_LABEL` 淨化覆寫），支援貼 URL 前後附帶個人觀點／疑問（含緊貼中文、大小寫 `HTTPS://`/`WWW.` 正規化、Wikipedia 括號與 IPv6 保護、單字筆記保留與 >600 字長文防誤拆），以 `> ` blockquote + HTML/Markdown 結構淨化置頂於摘要與 Wiki（確保唯一 H1 與無裸 HTML 注入）並引導 LLM 生成 `### 💬 【針對筆記與疑問回應】`；同步強化 `process_user_input` 前置 SSRF 驗證、Clef 獨立提交 ID、Quick Reply 筆記配額限制（`min(600, max_chars // 4)`）與 FastAPI `SummarizeRequest.user_note` 4000 字元顯式／內聯筆記合併規則（顯式優先保留 3000 字＋剩餘預算給內聯筆記）。
- **Telegram `/apikey` 單一金鑰管理與 4 層端點自動偵測 (`app/services/api_keys.py`, `app/api.py`, `app/legacy.py`)**：新增私訊專用 `/apikey` 指令與互動按鈕（產生、二次確認 Rotate 輪換、撤銷、cURL 用法），支援 `bot_scope` 跨環境 MongoDB 隔離（確定性 `_id`）、SHA-256 雜湊存儲與無正向快取即時撤權（與 `ALLOWED_USERS` 同步失效）、`API_TRUSTED_HOSTS` / `API_TRUST_PROXY_HEADERS` 防 Host Header Poisoning、跨行程 `fcntl.flock` JSON 備援保護，以及 `handle_button_click` 的 `ALLOWED_USERS` 權限守衛。
- **Python 3.14 基礎映像升級 (`Dockerfile`, `example.env`, `tests/test_dockerfile.py`)**：`Dockerfile` 升級至 `FROM python:3.14-slim`，補齊 `API_PUBLIC_URL`、`API_TRUSTED_HOSTS`、`API_TRUST_PROXY_HEADERS`、`API_KEYS_FILE` 說明，並於 `tests/test_api_keys.py` 與 `tests/test_dockerfile.py` 補齊完整安全回歸測試。
- **LLM 整合產出 SEO 繁體中文標題**：單次 LLM 呼叫同步產出「專業知識＋好奇心反差」SEO 標題與摘要，主標題完全取代原標題並於文章底部來源上方標註 `🏷️ 原始標題：{raw_title}`；FastAPI `SummarizeResponse` 新增選用欄位 `original_title`，並統一淨化原始標題與郵件主旨。
- **「📱 社群貼文風」重構為單篇高互動純文字爆文版**：`build_transform_prompt("social")` 改為繁中 220～320 字（< 400 字元）／英文 55–85 words（< 450 字元）、帶個人觀點／犀利吐槽、零 Markdown 的 Threads / X 爆文，並以 `clean_social_post_output` 確保純文字清理與 480 字元長度保護。
- **Telegram HTML 安全分片、失敗攔截與 Wiki 頁首保護**：新增 `app/services/telegram_delivery.py`（段落邊界安全切分、單塊 HTML 失敗獨立降級不重送已送出前段）、`is_summary_error_message` 明確攔截失敗或空回應（API 回傳 503），以及 `prepare_wiki_content` 保護 Wiki 首行唯一 H1 與來源資訊。

---

## 2026-11-17

### Changed & Improved
- **上游套件升級與依賴精簡**：升級 `python-telegram-bot`、`trafilatura` 與 `firecrawl-anydoc` 最低版本需求，並明確補列直接依賴 `requests` 與 `pydantic`。
- **移除過時與未使用依賴**：移除 `asyncio`、`youtube_transcript_api`、`litellm` 與 `openai`，同步清理 `app/legacy.py` 與 `main.py` 未使用的匯入。
- **掃描影像 PDF 錯誤處理**：於 `app/services/content.py` 捕捉 `anydoc.NeedsOcrError`，對無內嵌文字層的掃描 PDF 回傳友善提示，並在 `tests/test_content.py` 補齊單元測試。
- **建置與更新腳本修正**：更新 `Dockerfile` 之 Deno 官方安裝腳本網址；`auto_update_ytdlp.sh` 改用 `packaging.version.Version` 並保留 `pkg_resources` 相容回退。

---

## 2026-11-08

### Added
- **YouTube 多語音軌繁中優先選擇**：優化 `yt-dlp` 音軌格式選擇器與字幕語言優先順序（繁體中文優先），並自動清理暫存多餘字幕檔。
- **外語標題 AI 在地化翻譯**：於 `app/services/content.py` 新增 `needs_title_localization` 與 `localize_title`，將非中文標題自動翻譯為繁中並保留原文對照。
- **Magpie Gateway 整合與多層備援**：於 `app/services/llm.py` 新增 `MAGPIE_API_KEY`、`MAGPIE_BASE_URL`、`MAGPIE_MODEL` 支援，提供主要推論端點、同節點模型別名重試與多級自動降級備援。

---

## 2026-10-29

### Fixed & Improved
- **自動化持續部署 (CD) 修復**：修正 `auto_update_ytdlp.sh` 動態路徑解析，標準化 `build.sh` 容器 Watchtower scope 標籤，並於私有主機部署專屬 `watchtower-summary`。

---

## 2026-10-28

### Added & Fixed
- **Clef-Flash System One 廣告與垃圾訊息智慧過濾**：新增 `app/services/decision.py`，支援雙節點自動容錯、記憶體/MongoDB/磁碟三層快取、`/adfilter` 開關與 Telegram 強制查看按鈕。
- **Pocket Casts (`pca.st`) 整合與安全性修補**：支援短網址展開與單集音訊解析；升級 `markdown` 修補 Dependabot 已知漏洞。

---

## 2026-09-24

### Added
- **雙容器映像檔倉庫發布**：GitHub Actions 工作流程同步發布至 Docker Hub 與 GitHub Container Registry (`ghcr.io`)。

---

## 2026-09-08

### Added
- **Google Magika 檔案類型識別與本機音訊轉錄**：整合 `magika` 進行本地檔案格式偵測與智慧分流，支援直接上傳音訊檔進行分段 Whisper ASR 逐字稿轉錄與摘要。

---

## 2026-09-03

### Fixed
- **LLM 空摘要與 Groq 413 截斷保護**：修正空回應投遞問題，支援 Groq API 413 Payload 自動截斷保護並更新支援模型清單。

---

## 2026-09-02

### Fixed & Security
- **七層安全審計與防護強化**：全面導入 SSRF 阻斷（私有 IP 與雲端中繼資料保護）、Prompt Injection 隔離標記、常數時間 Bearer Token 驗證、FastAPI 安全標頭、暫存檔生命週期清理與路徑穿越過濾。

---

## 2026-08-30

### Added & Changed
- **多級容錯 LLM 引擎**：支援多組 API Key 輪詢、Tier 1–20 自動探索、JSON 備援設定與 Gemini/Groq 同供應商模型別名自動容錯；CI 啟用 Node 24 JavaScript Actions 設定並移除追蹤中的 `__pycache__`。

---

## 2026-08-28

### Added & Fixed
- **5 段式結構化摘要與 Quick Reply 互動選單**：新增推薦續問問題、6 大底部快速切換按鈕與自然語言風格轉換，同步整合 `/wiki` 發布規範對齊（標題清理、純 Markdown 上傳與書籍閱讀模式）。
- **yt-dlp Cookies 動態解析強化**：修正唯讀掛載導致的寫入錯誤，並強化 HTML 解析降級機制。

---

## 2026-08-27

### Added
- **David888 Wiki 知識庫發布與讀取 (`/wiki`, `/wikiread`)**：支援長篇報告自動發布至 Wiki 並產出公開閱讀與簡報連結，防止模型輸出偽工具呼叫標籤。
- **888box 雲端資產儲存 (`/box`, `/boxstats`)**：支援多節點自動容錯備援並產出 CDN 下載直鏈。
- **自然 AI 對話與意圖分流**：區分日常對話、續問與摘要任務；Whisper ASR 改為預設輸出時間戳記並以 `.txt` 檔案傳送。
- **開發規範文件**：建立 `AGENTS.md` 規範檔案與測試流程。

---

## 2026-08-26

### Added & Changed
- **AnyDoc 文件解析引擎遷移與占卜指令**：以 `firecrawl-anydoc` 取代 `markitdown`，並新增 `/tarot` 塔羅占卜與 `/yiyu` 月老姻緣生肖合婚指令。
- **Docker 基礎映像調整**：固定使用 `python:3.12-slim` 並加入 `audioop-lts` 條件相容設定。

---

## 2026-08-11

### Added
- **GitHub Actions CI/CD**：新增 `.github/workflows/docker-build.yml` 自動建置與推送 Docker 映像檔。

---

## 2026-07-23

### Changed & Fixed
- **模組化重構與長媒體逾時控制**：將核心程式整理為 `app/` 套件結構（`config`、`runtime`、`api`、`repositories`、`services`），調高長影片下載與 ASR 逾時上限，並改善跨主機 Chrome 設定檔掛載相容性。

---

## 2026-07-21

### Added
- **FastAPI Web API 服務**：於單一容器內並行啟動 FastAPI (`8001`) 與 Telegram Bot，提供 `/health` 與受 Bearer Token 保護的 `/api/v1/summarize` 端點及 `SKILL.md` 規格。

---

## 2026-04-16

### Fixed & Removed
- **自動更新腳本與掛載修正**：同步 `auto_update_ytdlp.sh` 與 `build.sh` 之 `/chrome-data` 掛載設定，移除冗餘的靜態 Cookie 定時匯出腳本。

---

## 2026-04-15

### Added & Fixed
- **YouTube 反機器人驗證繞過與即時 Cookies 同步**：改以掛載即時 Chrome Profile 搭配 Deno 解算 JS 挑戰，並強化自動化更新排程。

---

## 2025-12-03

### Added & Changed
- **模型切換、解答之書與廣告過濾**：新增 `/model` 模型切換指令與 `/boa` 解答之書指令；`OPENAI_API_KEY` 重構支援 `LLM_API_KEY` 與 `LLM2_*` 備援配置；於系統提示詞加入業配廣告略過規則並清理過時匯入。

---

## 2025-11-19

### Added
- **多語言、多輪續問與 Podcast 平台支援**：新增 `/lang` 繁中/英文切換、`/context` 與 `/clear` 多輪對話管理，以及 Pocket Casts、SoundOn、Apple Podcast 摘要支援。
