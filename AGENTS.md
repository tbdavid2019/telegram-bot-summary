# Developer & AI Agent Directives (AGENTS.md)

This document defines the strict engineering guidelines, documentation protocols, and architecture rules for all AI coding agents and human developers contributing to `telegram-bot-summary`.

---

## 🚨 1. Mandatory Documentation Protocol (鐵律：必寫 Changelog 與 README)

Whenever you add new features, fix bugs, modify API endpoints, change dependencies, or refactor the codebase:

1. **`changelog.md` & `docs/changelog.md` MUST ALWAYS BE UPDATED**:
   - Use **date-based sections only** (no semantic version numbers): `## [YYYY-MM-DD] - Feature Title` (or append to today's date).
   - Keep root `changelog.md` and `docs/changelog.md` synchronized.
   - Categorize entries into `### ✨ Added`, `### 🔄 Changed & Improved`, or `### 🔧 Fixed`.
   - Clearly document what changed, why it changed, and relevant module/service paths.

2. **`README.md` MUST ALWAYS BE UPDATED**:
   - Ensure the **Features** list, **Core/New Features** section, and **Usage / Command Reference Tables** (`/start`, `/help`, `/lang`, `/model`, `/tarot`, `/yiyu`, `/yt2audio`, `/yt2text`, `/apikey`, etc.) are 100% up to date.
   - Update environment variable descriptions in tables if `.env` keys are added or modified.

3. **Never skip documentation**: Committing code without updating `changelog.md`, `docs/changelog.md`, and `README.md` is strictly prohibited.

---

## 🏗️ 2. Architecture & Code Synchronization Rules

1. **Canonical Package Entrypoints (`app/`) & Thin Root Shims**:
   - All production logic lives inside `app/` (`app/main.py`, `app/legacy.py`, `app/api.py`, `app/config.py`, `app/runtime.py`, `app/repositories/`, `app/services/`).
   - Root `main.py`, `api.py`, and `runtime.py` are **thin compatibility shims** re-exporting from `app.*` so direct root invocations (`python main.py`, `uvicorn api:app`) work without duplicating code. Never re-introduce mirrored logic into root files.

2. **Modular Services (`app/services/` & `app/repositories/`)**:
   - `app/config.py`: `Settings`, shared `get_mongo_client()` pool, `is_admin_user()`, bot profile & `/app/data` persistence helpers.
   - `app/repositories/summaries.py`: `SummaryRepository` with `bot_scope` tagging.
   - `app/services/api_keys.py`: Per-user single API key management (`oli_`), `bot_scope` isolation, 4-layer base URL discovery.
   - `app/services/box.py`: 888box cloud asset upload & stats with SSRF check and multi-node failover.
   - `app/services/content.py`: URL/note parsing, SSRF `is_safe_url()` + `safe_http_get()`, Magika detection, `AnyDoc` conversion, streaming Whisper ASR (`transcribe_local_audio`), title/summary helpers.
   - `app/services/decision.py`: Clef-Flash System One ad/spam filtering with Memory/MongoDB/atomic-disk cache.
   - `app/services/divination.py`: Tarot (`/tarot`) and Yinyuan/Zodiac (`/yiyu`) APIs.
   - `app/services/llm.py`: Multi-tier & multi-key LLM failover (`call_llm_with_fallback`).
   - `app/services/podcast.py`: Pocket Casts, SoundOn, Apple Podcast RSS extraction, TTL cache, and audio transcription.
   - `app/services/quick_reply.py`: Quick Reply inline keyboard, style transforms, social post cleanup.
   - `app/services/summarization.py`: Canonical `summarize()` and system prompts shared by Bot and FastAPI.
   - `app/services/telegram_delivery.py`: Telegram Markdown-to-HTML safe chunking and delivery.
   - `app/services/wiki.py`: David888 Wiki publisher/reader with path traversal protection.
   - Always use `await run_blocking(...)` from `app.runtime` for blocking CPU or I/O operations (LLM calls, yt-dlp downloads, ASR requests, file parsing, HTTP requests) to avoid blocking the Telegram/FastAPI event loop.

3. **Automated Unit Testing**:
   - All services must have test coverage under `tests/` (`test_content.py`, `test_divination.py`, `test_async_boundaries.py`, `test_audit_fixes.py`, etc.).
   - **Mandatory test check**: Before pushing, run `python3 -m unittest discover -s tests` (using the Python 3.14 environment) and ensure all tests pass with 0 failures/errors.

---

## 📄 3. Document Parsing & Audio ASR Standards

1. **Document Conversion (AnyDoc by Firecrawl)**:
   - **DO NOT** use or re-introduce `markitdown`.
   - Use `firecrawl-anydoc` (`anydoc.to_markdown(file_path)`) for parsing Word (DOCX), PowerPoint (PPTX), Excel (XLSX), PDF, EPUB, RTF into GitHub-Flavored Markdown (and direct UTF-8 read for plain text/CSV/code).
   - Use `convert_document_to_markdown(file_path)` from `app.services.content`.

2. **Whisper ASR Speech-to-Text**:
   - Groq Whisper API calls MUST request `response_format=verbose_json` via HTTPS `requests.post` (never expose API keys in `curl` CLI args).
   - All speech-to-text outputs MUST default to timestamped lines formatted as `[MM:SS]` or `[HH:MM:SS]` using `format_whisper_segments`.

3. **Telegram Long Text Delivery**:
   - Telegram has a hard limit of 4,096 characters per message.
   - Transcripts, full ASR transcriptions, and `/yt2text` outputs MUST be delivered directly as `.txt` files (`send_document`) to prevent chat flooding and avoid Telegram API rate limits (HTTP 429).
   - Normal summary responses under 4,000 characters should be sent as direct chat messages.

4. **888box Cloud Asset Storage & Multi-Endpoint Failover**:
   - Primary Endpoint: `https://box.david888.com`
   - Backup 1: `https://box.glsoft.ai`
   - Backup 2: `https://box.aiurl.tw`
   - Use `app/services/box.py` for all file and URL uploads; always ensure automated fallback across these 3 nodes.

5. **David888 Wiki Knowledge Base Publisher (`app/services/wiki.py`)**:
   - Endpoint: `https://wiki.david888.com/api`
   - Canonical Skill Spec: `https://wiki.david888.com/.well-known/agent-skills/david888-wiki-publisher/SKILL.md`
   - **PRIMARY PURPOSE (FOR LLM AGENTS)**: Deliver executive summary in chat accompanied by public **`shareUrl`**, **`presentUrl`** (`/present`), and **`bookUrl`** (`/book`) when the user requests Wiki/report generation or clicks `/wiki`. Never auto-publish casual chats purely by length.
   - **MANDATORY DOCUMENT STRUCTURE RULE**: Markdown documents MUST ALWAYS start with a level-1 `# Document Title` on the very first line. Never prefix with conversational filler. Place `[TOC]`, alerts, and blockquotes AFTER `# Document Title`.
   - **CRITICAL LINK RULE**: Always deliver `shareUrl` (`https://wiki.david888.com/share/<shareId>`), `presentUrl` (`<shareUrl>/present`), or `bookUrl` (`<shareUrl>/book`) to users. Never give internal edit `url`.
   - **DIRECT RAW MARKDOWN UPLOAD**: Prefer `Content-Type: text/markdown; charset=UTF-8` with query parameters (`?public=true&theme=tokyo-night&width=100%`) when publishing large markdown notes.
   - **CONTENT NEGOTIATION**: When reading notes from `/share/<id>`, send header `Accept: text/markdown` to retrieve pure raw markdown directly.
   - Default theme: `tokyo-night`.

---

## 🚀 4. Deployment Targets & Server Verification

| Target | Bot Account | Remote Host | Deployment Command / Path |
| :--- | :--- | :--- | :--- |
| **Public Bot** | `@quantaar_bot` | `ssh david@aicreate360.com` | `cd /home/david/telegram-bot-summary && git pull origin main && /home/david/telegram-build.sh` |
| **Private Bot** | `@oli_summary_bot` | `ssh bitnami@git.glsoft.ai` | `cd /home/bitnami/telegram-bot-summary && git pull origin main && DEPLOY_CONFIRM=1 ./build.sh` |

- **Docker Base Image**: Always use `python:3.14-slim` (with `audioop-lts; python_version >= '3.13'` in `requirements.txt`) to handle Python 3.13+ standard library changes (`audioop` removed since Python 3.13) cleanly.
- **Watchtower Auto-Deploy & Dual-Registry**:
  - Images are dual-published to both Docker Hub (`tbdavid2019/telegram-bot-summary:latest`) and GitHub Container Registry (`ghcr.io/tbdavid2019/telegram-bot-summary:latest`).
  - **Public Bot (`aicreate360.com`)**: Runs global `watchtower` configured with `DOCKER_API_VERSION=1.45`, `WATCHTOWER_POLL_INTERVAL=60`, monitoring all containers.
  - **Private Bot (`git.glsoft.ai`)**: Runs scoped `watchtower-summary` (`--label-enable --scope summary`, `DOCKER_API_VERSION=1.44`, `WATCHTOWER_POLL_INTERVAL=60`). The container `telegram-bot-summary` MUST include labels `com.centurylinklabs.watchtower.enable=true` and `com.centurylinklabs.watchtower.scope=summary`, and use image `tbdavid2019/telegram-bot-summary:latest` so that automated CD pulls and restarts succeed seamlessly.
