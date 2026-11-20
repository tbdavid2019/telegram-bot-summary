from pathlib import Path
import unittest


LEGACY_SOURCE = Path("app/legacy.py").read_text(encoding="utf-8")
CONTENT_SOURCE = Path("app/services/content.py").read_text(encoding="utf-8")
PODCAST_SOURCE = Path("app/services/podcast.py").read_text(encoding="utf-8")


class MainRuntimeGuardsTests(unittest.TestCase):
    def test_llm_request_has_a_timeout(self):
        llm_source = Path("app/services/llm.py").read_text(encoding="utf-8")
        self.assertIn("timeout=req_timeout", llm_source)
        self.assertIn("timeout=LLM_TIMEOUT_SECONDS", LEGACY_SOURCE)

    def test_mongo_client_is_only_created_when_uri_is_configured(self):
        self.assertIn("mongo_client = get_mongo_client(mongo_uri, timeout_ms=MONGO_TIMEOUT_MS) if mongo_uri else None", LEGACY_SOURCE)
        self.assertIn("summary_collection = mongo_client", LEGACY_SOURCE)

    def test_long_media_operations_use_dedicated_timeouts(self):
        self.assertIn('ASR_TIMEOUT_SECONDS = float(os.environ.get("ASR_TIMEOUT_SECONDS", os.environ.get("SUBPROCESS_TIMEOUT_SECONDS", "600")))', LEGACY_SOURCE)
        self.assertIn('MEDIA_DOWNLOAD_TIMEOUT_SECONDS = float(os.environ.get("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "900"))', LEGACY_SOURCE)
        self.assertIn("asr_timeout=ASR_TIMEOUT_SECONDS", LEGACY_SOURCE)
        self.assertIn("timeout=asr_timeout", CONTENT_SOURCE)
        self.assertIn("safe_http_get(audio_url, headers=BROWSER_HEADERS, stream=True, timeout=effective_dl_timeout)", PODCAST_SOURCE)
        self.assertIn('"socket_timeout": MEDIA_DOWNLOAD_TIMEOUT_SECONDS', LEGACY_SOURCE)
