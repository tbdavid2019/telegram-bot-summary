import unittest
from app.services.content import format_timestamp, format_whisper_segments, split_user_input, is_url


class TestContentHelpers(unittest.TestCase):
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
