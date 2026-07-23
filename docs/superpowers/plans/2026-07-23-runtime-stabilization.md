# Runtime Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep slow extraction, summarization, and optional integrations from blocking Telegram and FastAPI event loops.

**Architecture:** Add a narrow async-to-thread adapter around the current synchronous functions, then use it at the Telegram and FastAPI boundaries. Keep HTTP and MongoDB limits in the synchronous service functions so every caller receives bounded behaviour. Mongo persistence is represented by an optional collection rather than a localhost default.

**Tech Stack:** Python 3.13, asyncio, requests, pymongo, python-telegram-bot, FastAPI, unittest.

---

### Task 1: Create runtime helpers

**Files:**
- Create: `runtime.py`
- Test: `tests/test_runtime.py`

- [ ] **Step 1: Write the failing tests**

```python
import asyncio
import unittest
from unittest.mock import patch

from runtime import run_blocking


class RunBlockingTests(unittest.IsolatedAsyncioTestCase):
    async def test_runs_function_in_thread(self):
        with patch("runtime.asyncio.to_thread", return_value="done") as to_thread:
            result = await run_blocking(str.upper, "done")

        self.assertEqual("done", result)
        to_thread.assert_awaited_once_with(str.upper, "done")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_runtime -v`

Expected: FAIL because `runtime` does not exist.

- [ ] **Step 3: Implement the minimal helper**

```python
import asyncio
from collections.abc import Callable
from typing import Any


async def run_blocking(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
    if kwargs:
        from functools import partial
        return await asyncio.to_thread(partial(function, *args, **kwargs))
    return await asyncio.to_thread(function, *args)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m unittest tests.test_runtime -v`

Expected: PASS.

### Task 2: Bound synchronous external operations and optional MongoDB

**Files:**
- Modify: `main.py:35-175, 963-995`
- Test: `tests/test_main_configuration.py`

- [ ] **Step 1: Write failing configuration tests**

```python
import os
import sys
import unittest
from unittest.mock import patch


class MongoConfigurationTests(unittest.TestCase):
    def test_missing_mongo_uri_disables_collection(self):
        with patch.dict(os.environ, {"MONGO_URI": ""}, clear=False):
            sys.modules.pop("main", None)
            import main
        self.assertIsNone(main.summary_collection)

    def test_llm_request_uses_timeout(self):
        with patch.dict(os.environ, {"MONGO_URI": ""}, clear=False):
            sys.modules.pop("main", None)
            import main
        with patch("main.requests.post") as post:
            post.return_value.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
            post.return_value.raise_for_status.return_value = None
            self.assertEqual("ok", main.call_gpt_api("hello"))
        self.assertIn("timeout", post.call_args.kwargs)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest tests.test_main_configuration -v`

Expected: FAIL because `summary_collection` is created for an empty URI and the LLM POST has no timeout.

- [ ] **Step 3: Implement bounded configuration**

```python
HTTP_TIMEOUT_SECONDS = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "60"))
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "5000"))

mongo_client = None
summary_collection = None
if mongo_uri:
    mongo_client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
        connectTimeoutMS=MONGO_TIMEOUT_MS,
    )
    summary_collection = mongo_client["bot_database"]["summaries"]
```

Pass `timeout=HTTP_TIMEOUT_SECONDS` to the LLM and Discord `requests.post` calls. Guard the existing `insert_one` call with `if summary_collection is not None` and catch/log its failure.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest tests.test_main_configuration -v`

Expected: PASS.

### Task 3: Apply the async boundary to request handlers

**Files:**
- Modify: `main.py:1116-1143, 1410-1560, 1633-1653`
- Modify: `api.py:60-118`
- Test: `tests/test_api_async_boundary.py`

- [ ] **Step 1: Write the failing API boundary test**

```python
import unittest
from unittest.mock import AsyncMock, patch

from api import api_summarize, SummarizeRequest


class ApiAsyncBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_work_is_offloaded(self):
        request = SummarizeRequest(input="plain text")
        with patch("api.run_blocking", new_callable=AsyncMock, side_effect=[["plain text"], "summary"]):
            response = await api_summarize(request, token="test")
        self.assertEqual("summary", response.summary)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m unittest tests.test_api_async_boundary -v`

Expected: FAIL because `api.run_blocking` does not exist and `api_summarize` calls synchronous functions directly.

- [ ] **Step 3: Apply the adapter at async call sites**

```python
from runtime import run_blocking

# Example within an async handler
text_array = await run_blocking(process_user_input, user_input)
summary = await run_blocking(summarize, text_array, language, selected_model)
```

Use the same pattern for title lookup, outbound optional integrations, and file conversion. Do not offload Telegram SDK `await` calls.

- [ ] **Step 4: Run focused and full tests**

Run: `python3 -m unittest discover -s tests -v`

Expected: PASS without network, credentials, Chrome, or MongoDB.

### Task 4: Verify and document configuration

**Files:**
- Modify: `example.env`
- Modify: `README.md`
- Test: `tests/test_main_configuration.py`

- [ ] **Step 1: Add configuration documentation**

```dotenv
# External request and MongoDB connection limits
HTTP_TIMEOUT_SECONDS=60
MONGO_TIMEOUT_MS=5000
```

Document that leaving `MONGO_URI` empty disables summary persistence.

- [ ] **Step 2: Run verification**

Run: `python3 -m py_compile main.py api.py runtime.py && python3 -m unittest discover -s tests -v`

Expected: compilation succeeds and all new tests pass.

- [ ] **Step 3: Commit the implementation**

```bash
git add main.py api.py runtime.py tests example.env README.md docs/superpowers/plans/2026-07-23-runtime-stabilization.md
git commit -m "fix: prevent summary requests from blocking event loop"
```
