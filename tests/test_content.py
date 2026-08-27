import unittest
from app.services.content import (
    format_timestamp,
    format_whisper_segments,
    split_user_input,
    is_url,
    is_explicit_summary_request,
    is_wiki_or_report_request,
    sanitize_model_output,
)


class TestContentHelpers(unittest.TestCase):
    def test_is_wiki_or_report_request(self):
        self.assertTrue(is_wiki_or_report_request("你透過 david888 wiki 寫一個 英語對話給我。"))
        self.assertTrue(is_wiki_or_report_request("請幫我寫一份市場分析報告"))
        self.assertTrue(is_wiki_or_report_request("商務口說情境練習"))
        self.assertFalse(is_wiki_or_report_request("你好！今天會下雨嗎？"))
        self.assertFalse(is_wiki_or_report_request("1 + 1 等於多少"))

    def test_sanitize_model_output_with_pseudo_tool_call(self):
        raw_pseudo = '[CALL:/wiki {"slug":"biz-eng","title":"商務英語對話","content":"# 商務英語口說\\n\\n這是內容"}]'
        clean, title = sanitize_model_output(raw_pseudo)
        self.assertNotIn("[CALL:/wiki", clean)
        self.assertIn("# 商務英語口說", clean)
        self.assertEqual(title, "商務英語對話")

    def test_sanitize_model_output_normal_text(self):
        normal_text = "這是一般的 AI 回應，沒有任何工具標籤。"
        clean, title = sanitize_model_output(normal_text)
        self.assertEqual(clean, normal_text)
        self.assertEqual(title, "")

    def test_is_explicit_summary_request(self):
        self.assertFalse(is_explicit_summary_request("你好"))
        self.assertFalse(is_explicit_summary_request("今天台北天氣如何？"))
        self.assertFalse(is_explicit_summary_request("幫我寫一段 Python 排序代碼"))
        self.assertTrue(is_explicit_summary_request("總結這篇：機器學習很棒。"))
        self.assertTrue(is_explicit_summary_request("請摘要以下重點：\n1. A\n2. B"))
        self.assertTrue(is_explicit_summary_request("TLDR: this is a summary"))
        self.assertTrue(is_explicit_summary_request("幫我總結"))

    def test_format_timestamp_seconds_and_minutes(self):
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(5), "00:05")
        self.assertEqual(format_timestamp(65), "01:05")
        self.assertEqual(format_timestamp(3599), "59:59")

    def test_format_timestamp_hours(self):
        self.assertEqual(format_timestamp(3600), "01:00:00")
        self.assertEqual(format_timestamp(3665), "01:01:05")
        self.assertEqual(format_timestamp(7325), "02:02:05")

    def test_format_whisper_segments_with_segments(self):
        sample = {
            "text": "Hello world this is a test",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "Hello world"},
                {"start": 2.5, "end": 5.0, "text": "this is a test"}
            ]
        }
        formatted = format_whisper_segments(sample, offset_seconds=60.0)
        self.assertIn("[01:00] Hello world", formatted)
        self.assertIn("[01:02] this is a test", formatted)

    def test_format_whisper_segments_fallback_raw_text(self):
        sample = {
            "text": "Raw fallback text",
            "segments": []
        }
        formatted = format_whisper_segments(sample, offset_seconds=120.0)
        self.assertEqual(formatted, "[02:00] Raw fallback text\n")

    def test_split_user_input(self):
        text = "line 1\n\nline 2\n  \nline 3"
        self.assertEqual(split_user_input(text), ["line 1", "line 2", "line 3"])

    def test_is_url(self):
        self.assertTrue(is_url("https://example.com"))
        self.assertTrue(is_url("http://test.org/abc"))
        self.assertFalse(is_url("just plain text"))


if __name__ == "__main__":
    unittest.main()
