from pathlib import Path
import unittest


MAIN_SOURCE = Path("main.py").read_text(encoding="utf-8")


class MainRuntimeGuardsTests(unittest.TestCase):
    def test_llm_request_has_a_timeout(self):
        request_line = next(line for line in MAIN_SOURCE.splitlines() if 'requests.post(f"{api_base_url}/chat/completions"' in line)
        self.assertIn("timeout=HTTP_TIMEOUT_SECONDS", request_line)

    def test_mongo_client_is_only_created_when_uri_is_configured(self):
        self.assertIn("if mongo_uri:", MAIN_SOURCE)
        self.assertIn("summary_collection = None", MAIN_SOURCE)
        self.assertIn("serverSelectionTimeoutMS=MONGO_TIMEOUT_MS", MAIN_SOURCE)
