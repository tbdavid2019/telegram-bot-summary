from pathlib import Path
import unittest


class AsyncBoundaryTests(unittest.TestCase):
    def test_api_offloads_extraction_and_summary(self):
        source = Path("app/api.py").read_text(encoding="utf-8")
        self.assertIn("from app.runtime import run_blocking", source)
        self.assertIn("await run_blocking(process_user_input, user_input)", source)
        self.assertIn("await run_blocking(", source)

    def test_telegram_handlers_offload_long_running_processing(self):
        source = Path("app/legacy.py").read_text(encoding="utf-8")
        self.assertIn("await run_blocking(retrieve_video_transcript_from_url, url)", source)
        self.assertIn("await run_blocking(download_video_audio, url)", source)
        self.assertIn("await run_blocking(process_user_input, user_input)", source)
        self.assertIn("await run_blocking(\n        summarize,", source)
        self.assertIn("await run_blocking(convert_document_to_markdown, file_path)", source)
        self.assertIn("await run_blocking(save_summary, summary_data)", source)
        self.assertIn("await run_blocking(send_to_discord, discord_message)", source)
        self.assertIn("await run_blocking(_fetch_boa_answer)", source)
        self.assertIn("await run_blocking(set_my_commands, telegram_token)", source)
