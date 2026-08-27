# Developer & AI Agent Directives (AGENTS.md)

This document defines the strict engineering guidelines, documentation protocols, and architecture rules for all AI coding agents and human developers contributing to `telegram-bot-summary`.

---

## 🚨 1. Mandatory Documentation Protocol (鐵律：必寫 Changelog 與 README)

Whenever you add new features, fix bugs, modify API endpoints, change dependencies, or refactor the codebase:

1. **`docs/changelog.md` MUST ALWAYS BE UPDATED**:
   - Add a new dated section: `## [YYYY-MM-DD] - Feature Title` (or append to today's date).
   - Categorize entries into `### ✨ Added`, `### 🔄 Changed & Improved`, or `### 🔧 Fixed`.
   - Clearly document what changed, why it changed, and relevant module/service paths.

2. **`README.md` MUST ALWAYS BE UPDATED**:
   - Ensure the **Features** list, **Core/New Features** section, and **Usage / Command Reference Tables** (`/start`, `/help`, `/lang`, `/model`, `/tarot`, `/yiyu`, `/yt2audio`, `/yt2text`, etc.) are 100% up to date.
   - Update environment variable descriptions in tables if `.env` keys are added or modified.

3. **Never skip documentation**: Committing code without updating `docs/changelog.md` and `README.md` is strictly prohibited.

---

## 🏗️ 2. Architecture & Code Synchronization Rules

1. **Dual Entrypoint Synchronization**:
   - `app/legacy.py` (used when executed as package `app.main`) and `main.py` (legacy root mirror) **MUST BE KEPT IN EXACT SYNC**.
   - After editing `app/legacy.py`, sync changes to `main.py` (adjusting import paths `from app.runtime` -> `from runtime`, `from app.api` -> `from api`).

2. **Modular Services**:
   - Place domain logic under `app/services/`:
     - `app/services/content.py`: Web content extraction, document conversion (`AnyDoc`), and Whisper timestamp formatting.
     - `app/services/divination.py`: Tarot (`/tarot`) and Yinyuan/Zodiac (`/yiyu`) APIs.
   - Always use `await run_blocking(...)` from `app.runtime` for blocking CPU or I/O operations (LLM calls, yt-dlp downloads, ASR requests, file parsing) to avoid blocking the Telegram event loop.

3. **Automated Unit Testing**:
   - All services must have test coverage under `tests/` (`test_content.py`, `test_divination.py`, `test_async_boundaries.py`, etc.).
   - **Mandatory test check**: Before pushing, run `python3 -m unittest discover -s tests` and ensure all tests pass with 0 failures/errors.

---

## 📄 3. Document Parsing & Audio ASR Standards

1. **Document Conversion (AnyDoc by Firecrawl)**:
   - **DO NOT** use or re-introduce `markitdown`.
   - Use `firecrawl-anydoc` (`anydoc.to_markdown(file_path)`) for parsing Word (DOCX), PowerPoint (PPTX), Excel (XLSX), PDF, EPUB, RTF, CSV into GitHub-Flavored Markdown.
   - Use `convert_document_to_markdown(file_path)` from `app.services.content`.

2. **Whisper ASR Speech-to-Text**:
   - Groq Whisper API calls MUST request `response_format=verbose_json`.
   - All speech-to-text outputs MUST default to timestamped lines formatted as `[MM:SS]` or `[HH:MM:SS]` using `format_whisper_segments`.

3. **Telegram Long Text Delivery**:
   - Telegram has a hard limit of 4,096 characters per message.
   - Transcripts, full ASR transcriptions, and `/yt2text` outputs MUST be delivered directly as `.txt` files (`send_document`) to prevent chat flooding and avoid Telegram API rate limits (HTTP 429).
   - Normal summary responses under 4,000 characters should be sent as direct chat messages.

---

## 🚀 4. Deployment Targets & Server Verification

| Target | Bot Account | Remote Host | Deployment Command / Path |
| :--- | :--- | :--- | :--- |
| **Public Bot** | `@quantaar_bot` | `ssh david@aicreate360.com` | `cd /home/david/telegram-bot-summary && git pull origin main && /home/david/telegram-build.sh` |
| **Private Bot** | `@oli_summary_bot` | `ssh bitnami@git.glsoft.ai` | `cd /home/bitnami/telegram-bot-summary && git pull origin main && DEPLOY_CONFIRM=1 ./build.sh` |

- **Docker Base Image**: Always use `python:3.12-slim` (with `audioop-lts` in `requirements.txt`) to avoid Python 3.13 standard library removals (`audioop`) and slow C-extension wheel compilations.