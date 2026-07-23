# App Package Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic runtime implementation with an `app/` package while retaining all public Bot, API, configuration, and deployment contracts.

**Architecture:** `app.main` composes shared settings, services, repository, Bot, and FastAPI app. Both transports call the same application services. Root `main.py` and `api.py` are compatibility shims only; neither contains business logic.

**Tech Stack:** Python 3.13, asyncio, FastAPI, python-telegram-bot, requests, yt-dlp, pymongo, unittest, Docker.

---

### Task 1: Establish package and settings boundary

**Files:**
- Create: `app/__init__.py`, `app/config.py`, `app/runtime.py`
- Modify: `tests/test_runtime.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing settings tests**

```python
from unittest import TestCase
from unittest.mock import patch

class SettingsTests(TestCase):
    def test_uses_existing_timeout_environment_names(self):
        with patch.dict("os.environ", {"HTTP_TIMEOUT_SECONDS": "45", "SUBPROCESS_TIMEOUT_SECONDS": "300"}, clear=True):
            from app.config import Settings
            settings = Settings.from_env()
        self.assertEqual(45.0, settings.web_request_timeout_seconds)
        self.assertEqual(300.0, settings.asr_timeout_seconds)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_config -v`

Expected: FAIL because `app.config` does not exist.

- [ ] **Step 3: Implement `Settings` and move `run_blocking`**

```python
@dataclass(frozen=True)
class Settings:
    telegram_token: str
    web_request_timeout_seconds: float
    llm_timeout_seconds: float
    asr_timeout_seconds: float
    media_download_timeout_seconds: float

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram_token=os.environ.get("TELEGRAM_TOKEN", "xxx"),
            web_request_timeout_seconds=float(os.environ.get("WEB_REQUEST_TIMEOUT_SECONDS", os.environ.get("HTTP_TIMEOUT_SECONDS", "60"))),
            llm_timeout_seconds=float(os.environ.get("LLM_TIMEOUT_SECONDS", "180")),
            asr_timeout_seconds=float(os.environ.get("ASR_TIMEOUT_SECONDS", os.environ.get("SUBPROCESS_TIMEOUT_SECONDS", "600"))),
            media_download_timeout_seconds=float(os.environ.get("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "900")),
        )
```

- [ ] **Step 4: Run tests**

Run: `python3 -m unittest tests.test_config tests.test_runtime -v`

Expected: PASS.

### Task 2: Move pure services and persistence

**Files:**
- Create: `app/services/__init__.py`, `app/services/summarization.py`, `app/services/content.py`, `app/services/delivery.py`, `app/services/telegram_commands.py`
- Create: `app/repositories/__init__.py`, `app/repositories/summaries.py`
- Test: `tests/test_content_cleanup.py`, `tests/test_repositories.py`

- [ ] **Step 1: Write failing temporary-file cleanup test**

```python
class TemporaryFileCleanupTests(TestCase):
    def test_removes_audio_file_when_transcription_fails(self):
        with patch("app.services.content.os.remove") as remove, patch("app.services.content.subprocess.run", side_effect=TimeoutExpired("curl", 600)):
            with self.assertRaises(TimeoutExpired):
                transcribe_audio_chunk("/tmp/chunk.wav", settings)
        remove.assert_called_once_with("/tmp/chunk.wav")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_content_cleanup -v`

Expected: FAIL because the service function does not exist.

- [ ] **Step 3: Move functions without changing signatures or messages**

Move prompts and `call_gpt_api` to `summarization.py`; URL/video/podcast/ASR functions to `content.py`; Discord/email functions to `delivery.py`; Telegram command HTTP calls to `telegram_commands.py`; and optional Mongo logic to `repositories/summaries.py`. Wrap all temporary files in `try/finally`, e.g.:

```python
try:
    result = subprocess.run(command, capture_output=True, text=True, timeout=settings.asr_timeout_seconds)
    return parse_transcript(result.stdout)
finally:
    if os.path.exists(chunk_path):
        os.remove(chunk_path)
```

- [ ] **Step 4: Run focused tests**

Run: `python3 -m unittest tests.test_content_cleanup tests.test_repositories -v`

Expected: PASS.

### Task 3: Rebuild transports around services

**Files:**
- Create: `app/bot.py`, `app/api.py`, `app/main.py`
- Modify: `main.py`, `api.py`
- Test: `tests/test_transport_independence.py`

- [ ] **Step 1: Write failing transport-independence tests**

```python
class TransportIndependenceTests(TestCase):
    def test_api_does_not_import_root_main(self):
        source = Path("app/api.py").read_text()
        self.assertNotIn("from main import", source)

    def test_root_api_is_a_compatibility_export(self):
        self.assertIn("from app.api import app", Path("api.py").read_text())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_transport_independence -v`

Expected: FAIL because `app.api` does not exist.

- [ ] **Step 3: Implement the transport factories**

`app.bot.create_application(settings, services)` registers the existing commands and delegates handler work to services using `run_blocking`. `app.api.create_app(settings, services)` exposes the existing health and summary endpoints. `app.main.main()` starts both. Root wrappers are:

```python
# main.py
from app.main import main
import asyncio
if __name__ == "__main__":
    asyncio.run(main())

# api.py
from app.api import app
```

- [ ] **Step 4: Run transport tests**

Run: `python3 -m unittest tests.test_transport_independence -v`

Expected: PASS.

### Task 4: Package and deployment safety

**Files:**
- Modify: `Dockerfile`, `build.sh`, `README.md`, `docs/changelog.md`
- Modify: `tests/test_dockerfile.py`
- Create: `tests/test_build_script.py`

- [ ] **Step 1: Write failing Docker and deployment tests**

```python
class DockerfileTests(TestCase):
    def test_runs_package_entrypoint(self):
        source = Path("Dockerfile").read_text()
        self.assertIn("COPY app /app/app", source)
        self.assertIn('ENTRYPOINT ["python3", "-u", "-m", "app.main"]', source)

class BuildScriptTests(TestCase):
    def test_requires_deploy_confirmation(self):
        source = Path("build.sh").read_text()
        self.assertIn("DEPLOY_CONFIRM", source)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_dockerfile tests.test_build_script -v`

Expected: FAIL because Docker still copies root files and the script replaces containers unconditionally.

- [ ] **Step 3: Implement package-aware Docker and safe deployment**

Docker copies `app/` and starts `app.main`. `build.sh` always builds, but only stops/removes/runs the production container when `DEPLOY_CONFIRM=1`; otherwise it prints the exact deployment command.

- [ ] **Step 4: Run full verification**

Run: `python3 -m py_compile $(find app -name '*.py' -print) main.py api.py && python3 -m unittest discover -s tests -v && docker build -t telegram-bot-summary:test .`

Expected: compilation, tests, and Docker build PASS.

- [ ] **Step 5: Commit and deploy**

```bash
git add app main.py api.py Dockerfile build.sh README.md docs/changelog.md tests
git commit -m "refactor: split application into app package"
git push
ssh bitnami@git.glsoft.ai 'cd <deployment-directory> && git pull && DEPLOY_CONFIRM=1 ./build.sh'
```
