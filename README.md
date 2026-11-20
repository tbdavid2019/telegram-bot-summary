
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
👤 用戶: https://pca.st/9wirf5m8 或 https://pocketcasts.com/podcast/...
🤖 Bot: 📌 EP718 你在「財富階梯」的哪一階？你想上升到哪一階？你打算怎麼做？ - 大人的Small Talk

       [自動識別為 Pocket Casts / pca.st 短網址]
       [自動對接官方 API 精準定位特定單集或最新一集音訊]
       [下載音頻 → Whisper 轉錄 → 生成真實標題與結構化摘要]

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
🤖 Bot: [單篇 220～320 字高互動純文字爆文：強反差 Hook + 個人觀點／犀利吐槽 + 零 Markdown，可直接一鍵複製貼上 Threads / X]
```

### 場景 12: 🛡️ Clef 決策模型廣告過濾與強制查看
```
👤 用戶: [傳送含有高宣傳廣告、股市飆股引流或行銷文案的連結/短文]
🤖 Bot: 🚫 【廣告內容已自動隱藏】

       經 Clef 決策模型判定，此內容包含高度商業宣傳、廣告行銷或垃圾訊息，已自動隱藏。

       💡 若您仍需要對此內容生成摘要，可點擊下方按鈕強制查看。
       [按鈕: 👁️ 仍要查看摘要]

👤 用戶: [點擊 👁️ 仍要查看摘要]
🤖 Bot: ⚡ 正在為您強制生成摘要，請稍候...
       📌 [廣告內容標題]
       [輸出完整摘要與重點整理]

👤 用戶: /adfilter
🤖 Bot: 🛡️ 廣告決策過濾設定 (Ad Filter)
       當前狀態：🟢 已開啟 (預設)
       決策節點：自建 Clef-Flash (<200ms) + 備援節點容錯
       超時設定：30 秒
       功能說明：自動偵測並隱藏推廣廣告、行銷垃圾與投資詐騙引流訊息，省去不必要的 AI 總結與 Token 消耗。
       [按鈕: 🟢 開啟過濾]  [按鈕: 🔴 關閉過濾]
```

### 場景 13: 🔑 個人 Web API Key 管理與 cURL 使用教學（限私訊）
```
👤 用戶: /apikey
🤖 Bot: 🔑 【個人 Web API Key 管理】
       目前尚未產生 API Key（每位用戶僅限 1 把有效金鑰，不保存明文）。
       🌐 偵測 API 端點：https://summary-api.example.com（來源：環境變數 API_PUBLIC_URL）
       [按鈕: 🔑 產生我的 API Key]  [按鈕: 📖 查看 cURL 用法]

👤 用戶: [點擊 🔑 產生我的 API Key]
🤖 Bot: 🔑 API Key 產生成功
       ⚠️ 完整金鑰僅顯示這一次：oli_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
       📖 完整 cURL 使用教學（含 /health 與 /api/v1/summarize 範例）
       [按鈕: 🔄 Rotate 輪換金鑰]  [按鈕: 🗑️ 撤銷金鑰]  [按鈕: 📖 查看 cURL 用法]
```

---

## 核心與新增功能

- **📝 網址附帶 `[ DAVID888 筆記／觀點備註 ]` 與 AI 專屬回應段落 (`app/services/content.py`, `app/legacy.py`, `app/api.py`)**：在 Telegram 貼上網址時（支援 URL 在前或觀點在前，包含緊貼中文如 `https://example.com這篇不錯`），可直接附帶個人筆記、評論或疑問；系統透過線性 O(n) `parse_url_and_user_note` 智慧拆出乾淨 URL 與備註（含 `http`/`https` 大小寫與主機名稱正規化、Wikipedia 括號與 IPv6 網址保護、單字筆記如「讚／推」保留，以及**長文保護**：當 URL 非位於開頭且剩餘字元 `> 600` 時視為長文中夾帶連結不誤拆），將經 Markdown/HTML 淨化與引用隔離的 `### 📝 [ DAVID888 筆記／觀點備註 ]`（支援 `AUTHOR_NOTE_LABEL` 自訂標題）置於摘要最上方，並引導 LLM 於結構化摘要前段生成 `### 💬 【針對筆記與疑問回應】`（英文版為 `### 💬 【Response to Your Note & Questions】`）專段直接回應；同步支援 David888 Wiki 發布、Quick Reply 風格轉換（筆記配額上限 `min(600, max_chars // 4)` 保護摘要主體）、Clef 強制查看與 FastAPI `user_note` 欄位。
- **🔑 Telegram `/apikey` 單一金鑰管理與 4 層端點自動偵測 (`app/services/api_keys.py`)**：支援私訊使用 `/apikey` 自助產生個人 `oli_...` Bearer Token，每位 `(bot_scope, telegram_id)` 用戶嚴格限制僅保留 **1 把有效金鑰**（僅於建立/輪換當下顯示一次明文，後端採 SHA-256 雜湊與常數時間 `hmac.compare_digest` 比對，絕不落盤明文）。支援 `bot_scope` 跨環境隔離（共用同一個 MongoDB 時 `@oli_summary_bot` 與 `@quantaar_bot` 金鑰互不干擾）、即時授權驗證（無正向快取，Rotate 輪換與撤銷零延遲 401 失效；自 `ALLOWED_USERS` 移除成員亦即時失效）、以及 **4 層智慧 API Base URL 偵測**（`API_PUBLIC_URL` $\rightarrow$ 僅於設定 `API_TRUSTED_HOSTS` 且經認證請求才記錄之受信任外部 Host $\rightarrow$ 公網 IP + `API_PORT` $\rightarrow$ `localhost:API_PORT`）與即貼即用的 cURL 教學。
- **🛡️ Clef-Flash System One 決策模型廣告與垃圾訊息智慧過濾**：整合自建 Clef-Flash 決策推論引擎（極速推論 <200ms、免外部 Token 費用），採用雙節點高可用容錯（Primary: `https://clef.create360.ai/v1/systemone` | Fallback: `https://clef.aiurl.tw/v1/systemone`），預設開啟並設定 30 秒逾時保護。若判定為廣告行銷訊息將直接隱藏輸出，並附帶 `[👁️ 仍要查看摘要]` 按鈕供用戶隨時強制查看；支援三層式快取架構（Memory $\rightarrow$ MongoDB $\rightarrow$ Disk），後續用戶讀取相同內容無需重複推論；雙節點皆異常時自動平滑降級放行，確保系統 100% 穩定可用。
- **🎙️ Pocket Casts 與 pca.st 短網址深度整合**：原生支援 Pocket Casts (`pocketcasts.com`, `play.pocketcasts.com`) 與官方短網址 (`pca.st`)，自動解析單集 UUID 並透過 Pocket Casts API 直接鎖定單集音訊與真實標題，無懼 CloudFront/AWS WAF 挑戰，經由 Whisper 轉錄輸出高精確逐字稿與重點摘要。
- **🎛️ 底部 Quick Reply 互動選單與無縫風格切換**：摘要下方自動附帶 6 大隨點隨轉按鈕（1分鐘極簡版、結構化大綱、核心 Q&A、社群貼文風、🎨 繪製概念圖、發布至 Wiki）；亦支援在聊天室直接以自然語言（如「轉社群風」、「給我大綱」、「畫概念圖」）自由切換！Quick Reply 優先採用濃縮後的標題與摘要作為轉換素材（不再被長逐字稿開頭截斷），其中 `1min`、`outline`、`qa` 支援 Telegram HTML 安全分片與單塊純文字降級排版，而「**📱 社群貼文風**」專為 Threads / X 打造為單篇繁中 220～320 字（< 400 字元）／英文 55–85 words（< 450 字元）、帶個人觀點與適度犀利吐槽的零 Markdown 純文字爆文，長按即可一鍵複製發布。
- **⚡ 5 段式結構化摘要與推薦續問**：標準產出容易懂、總結、觀點評論、重點條列、測驗三題、💡 推薦 3 個深入續問問題，兼具深度與互動性。
- **David888 Wiki 知識庫發布（LLM 深度報告好讀版）**：整合 `https://wiki.david888.com/api`，當使用者交代 LLM 撰寫長篇分析報告時，LLM 會自動將完整 Markdown 發布至 David888 Wiki，並回傳排版優美的公開閱讀連結（`shareUrl`）與 Reveal 2D 簡報模式（`presentUrl`）；亦可透過 `/wiki` 手動一鍵發布或 `/wikiread` 遠端讀取。
- **自然 AI 對話與智慧意圖分流**：日常打字（問候、編程諮詢、問題解答、隨意聊天）會以自然流暢的 AI 助理模式對話，並保留最近對話上下文；只有發送 URL、上傳文件或明確要求總結時，才會啟動結構化摘要。
- **888box 雲端資產儲存庫**：整合 888box（主要節點：`https://box.david888.com`，自動備援節點：`https://box.glsoft.ai`、`https://box.aiurl.tw`），提供 `/box <URL> [標題]` 遠端轉存各類影片、音訊、文件、圖片，自動產出 CloudFront 高速 CDN 下載直鏈與 Web 分享頁面，並可用 `/boxstats` 即時查看儲存統計。
- **AnyDoc 高效能文件解析**：採用 Firecrawl Rust 引擎 `firecrawl-anydoc>=0.2.4`（取代 MarkItDown），支援 PDF、Word (DOCX)、Excel (XLSX)、PowerPoint (PPTX)、EPUB、RTF、CSV 等文件極速轉為 Markdown 進行摘要，並可辨識無內嵌文字層的掃描影像 PDF（`NeedsOcrError`）給予友善提示。
- **塔羅占卜 (`/tarot`)**：支援單張、三張牌、鑽石、月亮、馬蹄鐵、塞爾特十字牌陣，提供抽牌正逆位展示與 AI 深度解牌指引。
- **月老姻緣與生肖合婚 (`/yiyu`)**：支援月老求籤解籤詩與出生年生肖契合度合婚測算。
- **Whisper ASR 時間戳聽寫**：調用 GROQ Whisper API，預設輸出 `[MM:SS]` 精確時間軸標記，並以 `.txt` 檔案直接下載。
- **多國語言 YouTube 繁中音軌優先與字幕優先**：支援 YouTube 多音軌配音影片，智慧優先選取繁體中文（`zh-Hant`、`zh-TW`、`zh-HK`）及中文音軌進行語音聽寫 (`audio_transcription`) 與音訊下載 (`/yt2audio`)；字幕提取自動優先配對繁體中文字幕。
- **🏷️ AI SEO 標題生成與原始標題對照**：單次 LLM 推論即可同時產出「專業知識＋好奇心反差」的部落格級繁體中文 SEO 標題與結構化摘要（零額外 API 呼叫成本），自動將簡體中文、外語或平庸網頁標題優化並完全取代為主標題；若有有效且不同的原始標題，會於文末來源連結上方保留 `🏷️ 原始標題：{raw_title}` 供對照，並同步套用於 Telegram 推播、David888 Wiki 發布、郵件主旨與 FastAPI `original_title` 欄位。
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
執行內建的設定腳本，這會啟動一個 Headless Chrome 容器，並將 `${HOME}/chrome-data` 掛載為設定目錄（同時僅於本機 `127.0.0.1` 綁定 WebUI Port `3000` 與 VNC Port `5900`）：
```bash
chmod +x setup_chrome_container.sh
./setup_chrome_container.sh
```

### 步驟 4: 登入 YouTube 建立真實 Session
1. Chrome 容器啟動後，可透過本機瀏覽器或 SSH Port Forwarding 存取 `http://127.0.0.1:3000`（或 VNC Port `5900`）。
2. 在裡面打開 YouTube 首頁並**登入你的 Google 帳號**。
3. 隨便點播 1-2 部影片，確定能正常播放（這會讓系統產生足夠的驗證 Token）。
4. 完成後就可以關閉該 WebUI 網頁。

### 步驟 5: Build 並啟動 Telegram Bot
執行 `build.sh`，它會自動打包 Bot 並掛載 Chrome 設定檔、`cookies.txt`（若有）與 `/app/data` 持久化目錄供 Bot 與 `yt-dlp` 使用：
```bash
DEPLOY_CONFIRM=1 ./build.sh
```

🎉 **完成！你的 Bot 現在已經可以順利繞過 YouTube 的機器人驗證並生成摘要了！**

---

👉 [telegram 示範機器人 小濃縮](https://t.me/quantaar_bot)

---

## Features

- **Per-User API Key Management (`/apikey`) & 4-Layer Endpoint Discovery**：支援透過私訊 `/apikey` 產生、Rotate 輪換與撤銷個人 `oli_...` Bearer Token，每位 `(bot_scope, telegram_id)` 嚴格限制僅保留 1 把金鑰；採確定性 `_id` 與 SHA-256 雜湊儲存、零正向快取即時撤銷驗證與 `ALLOWED_USERS` 同步檢查，並搭配 `API_TRUSTED_HOSTS` / `API_TRUST_PROXY_HEADERS` 防禦 Host Header Poisoning。
- **Clef-Flash System One Intelligent Ad & Spam Filtering**：原生整合自建 Clef 決策模型（推論延遲 <200ms），具備雙節點自動容錯備援（`clef.create360.ai` 與 `clef.aiurl.tw`），預設開啟並具備 30 秒防護逾時。自動識別商業推廣、行銷文案與投資詐騙訊息並隱藏輸出，附帶記憶體、MongoDB 與本地磁碟多層快取，並提供 `/adfilter` 開關與 Telegram 隨點強制查看按鈕。
- **Google Magika AI File Type Identification & Smart Routing**：整合 Google 開源深度學習檔案識別引擎 `Magika`（100+ 種格式，精確率 >99%），在 Docker 鏡像建構階段即將 ONNX 模型固化封裝，執行期純本地 CPU 毫秒級推論（1~5ms，零網路開銷）。智慧識別上傳內容並自動分流（音訊自動轉錄逐字稿、文檔交由 AnyDoc 轉檔、純文字直接讀取、不支援二進位檔友善阻絕）。
- **Audio Document Transcription (Whisper ASR)**：支援直接向 Telegram 機器人傳送錄音與音訊文件（`.mp3`, `.m4a`, `.wav`, `.ogg`, `.flac`, `.aac`, `.opus`），自動以 Groq Whisper (`whisper-large-v3`, `verbose_json`) 分塊轉錄，附帶精準時間戳記逐字稿文字檔 (`.txt`) 並產出結構化 AI 核心重點摘要。
- **7-Layer Defensive Security Architecture**：內建完整的 7 層安全審計防護，阻斷 SSRF（私有 IP/迴路/雲端中繼資料封鎖）、Prompt Injection 隔離標記、常數時間 Bearer Token 驗證、FastAPI 安全標頭、例外安全暫存檔生命週期清理與路徑穿越過濾。
- **Dual Container Registries (Docker Hub & GHCR)**：支援 Docker Hub (`tbdavid2019/telegram-bot-summary:latest`) 與 GitHub Container Registry (`ghcr.io/tbdavid2019/telegram-bot-summary:latest`) 雙來源自動建置與發布，免除對單一鏡像來源的依賴，大幅降低 Docker Hub 匿名限流風險。
- **Multi-Tier Fallback LLM Engine**：支援多級 LLM 容錯降級機制 (`LLM1` -> `LLM2` -> `LLM3` -> `Groq Fallback`)，當主要模型遭遇 HTTP 400、429 超流、500/503 或網路逾時，秒級自動切換備用端點，並自動修復 Google Gemini OpenAI 格式相容性。
- **Supports text**：處理純文本。
- **Supports URLs**：自動擷取各類網頁文章與新聞內容（基於 `trafilatura>=2.3.1`）。
- **Supports Documents & PDFs**：採用 Firecrawl Rust 引擎 `AnyDoc`（`firecrawl-anydoc>=0.2.4`），全面支援 PDF、Word (`.docx`)、PowerPoint (`.pptx`)、Excel (`.xlsx`)、EPUB、RTF、CSV 等文件極速轉為 Markdown 並進行 AI 摘要。
- **Modern Telegram Bot Engine**：基於 `python-telegram-bot>=22.8`（Python 3.14+ / `python:3.14-slim`），全面支援最新 Telegram Bot API 與非同步互動體驗。
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
| /tarot [牌陣] [問題] | 塔羅抽牌與 AI 深度解讀 (支援單張/三張/鑽石/月亮/馬蹄鐵/塞爾特十字牌陣) |
| /yiyu [模式] [問題] | 月老姻緣求籤與生肖合婚契合度測算（別名 `/yinyuan`） |
| /boa | 解答之書 Book of Answers |
| /context | 顯示當前對話上下文 |
| /clear | 清除對話歷史 |
| /yt2audio <URL> | 下載影片音頻 |
| /yt2text <URL> | 將影片轉成帶時間戳的逐字稿文字檔 (`.txt`) |
| /box <URL> [標題] | 將遠端影片、音訊、圖片、文件轉存至 888box 雲端（公開模式限管理員） |
| /boxstats | 查看 888box 當前儲存的資產總數與分類統計（公開模式限管理員） |
| /wiki [標題/內容] | 發布至 David888 Wiki 知識庫 (產出公開好讀版與投影片) |
| /wikiread <路徑> | 讀取 David888 Wiki 頁面內容 |
| /adfilter | 查看或切換廣告決策過濾狀態 (預設開啟，附帶隨點強制查看按鈕) |
| /apikey | 產生/輪換/撤銷個人 Web API Key 與查看自動偵測端點之 cURL 用法（限私訊） |

### 💡 使用技巧

1. **直接發送內容**: 文字、網址、各類文件檔案（PDF、Word、Excel、PPT、EPUB、CSV、TXT）或直接傳送錄音/音訊檔（MP3、M4A、WAV、OGG、AAC 等），機器人會透過 Google Magika 自動識別內容類型，分流至 Whisper 逐字稿轉錄或 AnyDoc 文檔摘要，無需手動指定格式。
2. **網址附帶個人筆記／觀點**: 貼上 URL 時可在前後附上個人評論、筆記或疑問，Bot 會將 `[ DAVID888 筆記／觀點備註 ]` 置於摘要最上方並由 AI 專段直接回應。
3. **續問功能**: 完成摘要後，直接發送問題即可續問
4. **語言切換**: 使用 `/lang` 切換語言後，之後的摘要都使用新語言
5. **多輪對話**: 系統自動保留最近 3 輪對話，支援深入討論
6. **新對話**: 發送新 URL 或 `/clear` 開始新的摘要

### Docker 設置指南

#### 影片處理

若要處理需要登入才能觀看的影片，請依照以下步驟：

在本地電腦執行以下命令來導出 cookies：

```bash
yt-dlp --cookies-from-browser chrome --cookies cookies.txt
```

將產生的 cookies.txt 檔案放入專案根目錄

#### 2. 自動化 Chrome Docker 方案 (推薦)

1. **運行 Chrome 容器**：使用 `./setup_chrome_container.sh` 啟動 `linuxserver/chromium` 並持久化 `${HOME}/chrome-data`。
2. **Volume 即時掛載**：透過 `DEPLOY_CONFIRM=1 ./build.sh`（或指定 `CHROME_DATA_DIR`），直接掛載 Chrome Profile 與選用 `cookies.txt` 給 Bot 使用。

詳細變更記錄請參閱 [changelog.md](changelog.md)（或 [docs/changelog.md](docs/changelog.md)）。

#### 3. 拉取 Docker 映像
支援從 **Docker Hub** 或 **GitHub Container Registry (GHCR)** 雙來源拉取映像：

```bash
# 從 Docker Hub 拉取
docker pull tbdavid2019/telegram-bot-summary:latest

# 或從 GitHub Container Registry (GHCR) 拉取
docker pull ghcr.io/tbdavid2019/telegram-bot-summary:latest
```

#### 4. 運行 Docker 容器
執行以下命令來運行容器（請先備妥 `.env`）：
```bash
docker run -d \
    --name telegram-bot-summary \
    --restart unless-stopped \
    -p 8001:8001 \
    -v "$PWD/data:/app/data" \
    --env-file .env \
    tbdavid2019/telegram-bot-summary:latest
```

#### 5. 環境變數說明

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
| `MAGPIE_API_KEY` | 自建 Magpie Gateway API 金鑰 (若設置自動作為 Tier 0 主要推論模型) |
| `MAGPIE_MODEL` | Magpie Gateway 模型名稱 (預設: `auto/gemini-3.8-flash`) |
| `MAGPIE_BASE_URL` | Magpie Gateway 基礎 URL (預設: `http://60.248.142.126:3425/v1`) |
| `LLM_API_KEY` / `OPENAI_API_KEY` | 主要 LLM API 金鑰 (當 MAGPIE 啟用時自動作為備援 Tier 1) |
| `LLM_MODEL` | 主要 LLM 模型名稱 (預設: `gpt-4o-mini`) |
| `LLM_BASE_URL` | 主要 LLM API 基礎 URL (預設: `https://api.openai.com/v1`) |
| `LLM2_API_KEY` / `LLM2_MODEL` / `LLM2_BASE_URL` | 備用 LLM 2 設定 (支援自動容錯降級) |
| `LLM3_API_KEY` ~ `LLM20_API_KEY` | 備用 LLM 多級容錯設定 (可自由擴展至 LLM20) |
| `LLM_FALLBACK_MODELS` | 同節點備用模型列表 (逗號分隔) |
| `GROQ_API_KEY` | GROQ API 金鑰 (用於 Whisper 語音轉文字與自動 Groq LLM 降級) |
| `GROQ_FALLBACK_MODEL` | GROQ 自動備援模型名稱 (預設: `openai/gpt-oss-120b`，具備 413 Payload 自動截取保護) |
| `LLM_TIMEOUT_SECONDS` | LLM 呼叫逾時時間 (預設: `180` 秒) |

### Clef 決策模型變數 (廣告與垃圾訊息智慧過濾)

| Environment Variable | Description |
|-----------------------|-------------|
| `CLEF_PRIMARY_URL` | 主要 Clef 決策節點 (預設: `https://clef.create360.ai/v1/systemone`) |
| `CLEF_FALLBACK_URL` | 備援 Clef 決策節點 (預設: `https://clef.aiurl.tw/v1/systemone`) |
| `CLEF_TIMEOUT_SECONDS` | Clef 決策模型呼叫逾時時間 (預設: `30` 秒) |
| `DECISION_AD_FILTER_ENABLED` | 是否預設開啟廣告與行銷垃圾訊息過濾 (預設: `true`) |

### Bot Variables

| Environment Variable  | Description                                                        |
|------------------------|--------------------------------------------------------------------|
| `CHUNK_SIZE`          | 逐字稿/字幕最大分段字元數，程式預設 `2100`（`example.env` 範例為 `90000`） |
| `TELEGRAM_TOKEN`      | Telegram 機器人的 API 令牌                                        |
| `USE_AUDIO_FALLBACK`  | 是否啟用無字幕影片處理功能，`1` 表示啟用，`0` 表示禁用           |
| `ALLOWED_USERS`       | 允許使用機器人的用戶 ID 列表，用逗號分隔（公開模式留空）          |
| `ADMIN_USERS`         | 允許執行 `/box`、`/boxstats` 等敏感管理指令的 Telegram User ID 列表 |
| `PUBLIC_ALLOW_PRIVILEGED_COMMANDS` | 公開模式（`ADMIN_USERS` 與 `ALLOWED_USERS` 皆空）是否開放 `/box` 等權限指令；預設 `0`（禁用） |
| `SHOW_PROCESSING`     | 是否顯示處理中訊息，`1` 表示啟用，`0` 表示禁用                   |
| `AUTHOR_NOTE_LABEL`   | 選用；自訂網址附帶筆記區塊標題（預設：`[ DAVID888 筆記／觀點備註 ]`） |
| `BOT_DISPLAY_NAME` / `BOT_TAGLINE` | 選用；自訂機器人顯示名稱與摘要頁尾標籤               |
| `BOT_DATA_DIR`        | 選用；統一本地持久化目錄（掛載 `/app/data` 時自動偵測），存放 `bot_persistence.pkl` 與預設 `api_keys.json` |
| `BOT_PERSISTENCE_PATH` | 選用；覆寫 PTB 狀態持久化檔案路徑（預設 `<BOT_DATA_DIR>/bot_persistence.pkl`） |
| `GROQ_FALLBACK_KEYS`  | 選用；Groq 備用金鑰列表（逗號分隔，與 `GROQ_API_KEY` 合併輪替使用） |

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
# 從 GHCR 或 Docker Hub 更新（建議直接使用 DEPLOY_CONFIRM=1 ./build.sh 以自動保留所有掛載與標籤）
docker pull ghcr.io/tbdavid2019/telegram-bot-summary:latest
docker stop telegram-bot-summary && docker rm telegram-bot-summary
docker run -d \
    --name telegram-bot-summary \
    --restart unless-stopped \
    --label com.centurylinklabs.watchtower.enable=true \
    --label com.centurylinklabs.watchtower.scope=summary \
    -p 8001:8001 \
    -v "$PWD/data:/app/data" \
    -v "$HOME/chrome-data:/chrome-data" \
    --env-file .env \
    ghcr.io/tbdavid2019/telegram-bot-summary:latest
```

---

## 新增 `.env`

完整且最新之環境變數範本請直接參閱並複製 [`example.env`](example.env)（包含 `MAGPIE_*`、`LLM1~20_*`、`LLM_FALLBACK_CONFIGS`、`GROQ_*`、`CLEF_*`、`BOX_*`、`WIKI_*`、`ADMIN_USERS`、`API_*` 等完整設定）。

---

## 🌐 Web API 服務與 LLM Skill 整合

本專案除了提供 Telegram Bot 介面外，亦內建了高效率的 **FastAPI Web 服務**，能讓任何外部 LLM（如 Custom GPTs、Claude Projects、LangChain / LlamaIndex 代理）或第三方應用系統直接經由 HTTP POST 取得結構化的 Markdown 摘要。

### 1. 環境變數設定 (`.env`)

在 `.env` 中加入以下設定即可啟用或配置 API 存取：

| 環境變數 | 說明 | 預設值 / 範例 |
| --- | --- | --- |
| `API_AUTH_TOKENS` | API 金鑰驗證清單（多組請用逗號分隔） | `token1,token2,token3` |
| `API_PORT` | Web API 服務監聽埠 | `8001` |
| `API_PUBLIC_URL` | 選用；對外公開 API 基礎網址（供 `/apikey` 產生 cURL 指令，留空時自動偵測） | `https://summary-api.example.com` |
| `API_TRUSTED_HOSTS` | 選用；逗號分隔允許觀測記錄的外部 Hostname 白名單（不含 port）；留空停用動態 Host 學習 | `summary-api.example.com` |
| `API_TRUST_PROXY_HEADERS` | 選用；僅於信任反向代理時設為 `true` 才讀取 `X-Forwarded-Proto` / `X-Forwarded-Host` | `false` |
| `API_KEYS_FILE` | 選用；未設定 `MONGO_URI` 時之動態 API Key 本地 JSON 儲存路徑 | `<BOT_DATA_DIR>/api_keys.json`（未掛載時為記憶體模式） |
| `WEB_REQUEST_TIMEOUT_SECONDS` | Webhook、SMTP 等一般外部服務的最長等待秒數 | `60` |
| `LLM_TIMEOUT_SECONDS` | 單次 LLM 摘要/問答呼叫的最長等待秒數 | `180` |
| `ASR_TIMEOUT_SECONDS` | 每段 Whisper ASR 轉錄的最長等待秒數 | `600` |
| `MEDIA_DOWNLOAD_TIMEOUT_SECONDS` | Podcast/影片音訊下載的最長等待秒數 | `900` |
| `MONGO_TIMEOUT_MS` | MongoDB 連線逾時毫秒數 | `5000` |

> 💡 *若未設定 `API_AUTH_TOKENS`，系統會在啟動時動態產生內部隨機 Token（基於安全考量不寫入日誌；正式環境請於 `.env` 設定 `API_AUTH_TOKENS` 或透過私訊 `/apikey` 產生個人金鑰）。*

> 💡 *若 `MONGO_URI` 留空，Bot 會略過摘要儲存，仍會正常回覆 Telegram 與 API 請求。*

### 2. API 端點規格

#### 外部端點 (Default Port: `8001`)

* **`GET /health`**：存活檢查（Liveness）
* **`GET /readyz`**：就緒檢查（MongoDB 與 Bot Polling 狀態）
* **`POST /api/v1/summarize`**：發送摘要請求
  * **Header**: `Authorization: Bearer <API_AUTH_TOKEN>`
  * **Body (JSON)**:
    ```json
    {
      "input": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "language": "zh-TW",
      "user_note": "選用（上限 4000 字元）：附上想讓 AI 直接回應的個人觀點、筆記或疑問"
    }
    ```
  * **`user_note` 合併與長文保護規則**：
    * 支援在 `input` 內聯「URL + 觀點」（支援 URL 在前或觀點在後）；若 URL **非位於開頭**且剩餘文字長度 `> 600` 字元，視為長文中夾帶連結而不拆出 `user_note`。
    * 若同時提供顯式 `user_note` 與 `input` 內聯筆記且兩者不同：總長度上限為 `4000` 字元；合計超過 `4000` 時，優先保留顯式 `user_note` 最多 `3000` 字元（若顯式筆記較短則保留全文），再將剩餘預算分配給內聯筆記（以 `\n\n` 串接）。
  * **Response (JSON)**:
    ```json
    {
      "status": "success",
      "title": "AI SEO 優化後標題",
      "original_title": "Original Video or Webpage Title",
      "original_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "summary": "### ⓵ 【容易懂 Easy Know】\n...",
      "is_ad": false
    }
    ```

### 3. LLM 介接 (SKILL.md)

專案根目錄下附有專門為 LLM 說明的指令檔 [`SKILL.md`](SKILL.md)，包含完整請求格式與 **OpenAPI 3.0 YAML** 規格，可直接匯入 OpenAI Custom GPTs Actions 或 Prompt 系統。

---

## 🚀 CI/CD 與自動化部署機制 (Continuous Deployment)

本專案採用 **GitHub Actions + Dual-Registry + Scoped Watchtower** 的自動化持續整合與部署架構：

1. **持續整合 (CI - GitHub Actions)**：
   - 每當程式推送到 `main` 分支，`.github/workflows/docker-build.yml` 自動觸發。
   - 映像檔同時雙發布至 **Docker Hub** (`tbdavid2019/telegram-bot-summary:latest`) 與 **GitHub Container Registry** (`ghcr.io/tbdavid2019/telegram-bot-summary:latest`)。

2. **持續部署 (CD - Watchtower 自動拉取與滾動重啟)**：
   - **公開 Bot (`@quantaar_bot` @ `aicreate360.com`)**：由主機全域 `watchtower` 容器每 60 秒輪詢更新。
   - **私有 Bot (`@oli_summary_bot` @ `git.glsoft.ai`)**：由專屬 `watchtower-summary` 容器（`--scope summary --label-enable`）每 60 秒輪詢更新，自動拉取最新映像檔並無縫重啟容器。

