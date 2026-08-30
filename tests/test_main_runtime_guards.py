from pathlib import Path
import unittest


MAIN_SOURCE = Path("main.py").read_text(encoding="utf-8")


class MainRuntimeGuardsTests(unittest.TestCase):
    def test_llm_request_has_a_timeout(self):
        llm_source = Path("app/services/llm.py").read_text(encoding="utf-8")
        self.assertIn("timeout=req_timeout", llm_source)
        self.assertIn("timeout=LLM_TIMEOUT_SECONDS", MAIN_SOURCE)

    def test_mongo_client_is_only_created_when_uri_is_configured(self):
        self.assertIn("if mongo_uri:", MAIN_SOURCE)
        self.assertIn("summary_collection = None", MAIN_SOURCE)
        self.assertIn("serverSelectionTimeoutMS=MONGO_TIMEOUT_MS", MAIN_SOURCE)

    def test_long_media_operations_use_dedicated_timeouts(self):
        self.assertIn('ASR_TIMEOUT_SECONDS = float(os.environ.get("ASR_TIMEOUT_SECONDS", os.environ.get("SUBPROCESS_TIMEOUT_SECONDS", "600")))', MAIN_SOURCE)
        self.assertIn('MEDIA_DOWNLOAD_TIMEOUT_SECONDS = float(os.environ.get("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "900"))', MAIN_SOURCE)
        self.assertEqual(2, MAIN_SOURCE.count("timeout=ASR_TIMEOUT_SECONDS"))
        self.assertIn("requests.get(audio_url, stream=True, timeout=MEDIA_DOWNLOAD_TIMEOUT_SECONDS)", MAIN_SOURCE)
        self.assertGreaterEqual(MAIN_SOURCE.count("'socket_timeout': MEDIA_DOWNLOAD_TIMEOUT_SECONDS"), 2)
