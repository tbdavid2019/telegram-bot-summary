import os
import unittest
from unittest.mock import patch


class SettingsTests(unittest.TestCase):
    def test_uses_existing_timeout_environment_names(self):
        from app.config import Settings

        with patch.dict(os.environ, {"HTTP_TIMEOUT_SECONDS": "45", "SUBPROCESS_TIMEOUT_SECONDS": "300"}, clear=True):
            settings = Settings.from_env()

        self.assertEqual(45.0, settings.web_request_timeout_seconds)
        self.assertEqual(300.0, settings.asr_timeout_seconds)
