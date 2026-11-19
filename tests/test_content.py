import unittest
from app.services.content import (
    format_timestamp,
    format_whisper_segments,
    split_user_input,
    is_url,
    is_explicit_summary_request,
    is_wiki_or_report_request,
    is_conversation_followup,
    sanitize_model_output,
    detect_file_type,
    convert_document_to_markdown,
    transcribe_local_audio,
    needs_title_localization,
    localize_title,
    sanitize_raw_title,
    is_valid_raw_title,
    is_summary_error_message,
    _split_markdown_safely,
    extract_title_from_summary,
    resolve_final_title,
    compose_summary_with_source,
    prepare_wiki_content,
)


class TestContentHelpers(unittest.TestCase):
    def test_is_conversation_followup(self):
        history = {"summary": "這是文章摘要", "original_content": ["原文內容"]}
        self.assertTrue(is_conversation_followup("請問作者在文中提到的第三點是什麼？", history))
        self.assertTrue(is_conversation_followup("可以再解釋清楚一點嗎？", history))
        # Standalone requests must NOT be treated as follow-up to old summary
        self.assertFalse(is_conversation_followup("你透過 david888 wiki 寫一個 英語對話給我", history))
        self.assertFalse(is_conversation_followup("寫一個 Python 排序函數", history))
        self.assertFalse(is_conversation_followup("請幫我寫一份報告", history))
        self.assertFalse(is_conversation_followup("https://example.com", history))
        self.assertFalse(is_conversation_followup("問題", None))

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

    def test_detect_file_type_plain_text(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Hello world, this is a plain text file for testing.")
            fpath = f.name
        try:
            info = detect_file_type(fpath)
            self.assertIn(info["group"], ("text", "code"))
            self.assertTrue(info["is_text"])
            self.assertEqual(info["label"], "txt")
            self.assertEqual(info["mime_type"], "text/plain")
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    def test_detect_file_type_markdown(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            f.write(b"# Title\n\nThis is a markdown document.\n- Item 1\n- Item 2")
            fpath = f.name
        try:
            info = detect_file_type(fpath)
            self.assertIn(info["group"], ("text", "code"))
            self.assertTrue(info["is_text"])
            self.assertIn(info["label"], ("markdown", "txt", "md"))
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    def test_detect_file_type_fallback(self):
        from unittest.mock import patch
        with patch("app.services.content.get_magika", return_value=None):
            info = detect_file_type("some/dummy/path.py")
            self.assertEqual(info["label"], "py")
            self.assertTrue(info["is_text"])
            self.assertEqual(info["group"], "text")
            self.assertEqual(info["score"], 0.0)

    def test_convert_document_to_markdown_text(self):
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write("Line 1\nLine 2".encode("utf-8"))
            fpath = f.name
        try:
            content = convert_document_to_markdown(fpath)
            self.assertIn("Line 1", content)
            self.assertIn("Line 2", content)
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    def test_convert_document_to_markdown_unsupported_archive(self):
        from unittest.mock import patch
        fake_info = {
            "group": "archive",
            "label": "zip",
            "description": "Zip archive",
            "is_text": False,
            "extensions": ["zip"],
            "mime_type": "application/zip",
        }
        with patch("app.services.content.detect_file_type", return_value=fake_info):
            with self.assertRaises(ValueError) as ctx:
                convert_document_to_markdown("archive.zip")
            self.assertIn("不支援的檔案格式", str(ctx.exception))

    def test_transcribe_local_audio_mocked(self):
        from unittest.mock import patch, MagicMock
        import json

        mock_audio = MagicMock()
        mock_audio.__len__.return_value = 50000  # 50s
        mock_audio.__getitem__.return_value = mock_audio

        mock_resp = {
            "text": "這是本地音訊轉錄測試",
            "segments": [
                {"start": 0.0, "end": 2.5, "text": "這是本地音訊轉錄測試"}
            ]
        }
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(mock_resp)

        with patch("pydub.AudioSegment.from_file", return_value=mock_audio), \
             patch("subprocess.run", return_value=mock_result), \
             patch("os.path.exists", return_value=False):
            transcript = transcribe_local_audio("/tmp/fake_audio.mp3")
            self.assertIn("[00:00] 這是本地音訊轉錄測試", transcript)

    def test_needs_title_localization(self):
        # Spanish title from YouTube test case
        self.assertTrue(needs_title_localization("¿Quién ha sido el más RICO de la historia?"))
        # English titles
        self.assertTrue(needs_title_localization("How to build an AI agent in 2026"))
        self.assertTrue(needs_title_localization("OpenAI vs Google DeepMind"))
        # Japanese title with Hiragana/Katakana
        self.assertTrue(needs_title_localization("【最新】日本の経済危機について"))
        self.assertTrue(needs_title_localization("プログラミング入門"))
        # Korean title
        self.assertTrue(needs_title_localization("인공지능의 미래"))
        # Already in Traditional or Simplified Chinese
        self.assertFalse(needs_title_localization("【老高與小茉】五大歷史謎團"))
        self.assertFalse(needs_title_localization("台灣人工智慧發展趨勢分析"))
        # Generic or empty titles
        self.assertFalse(needs_title_localization("影片"))
        self.assertFalse(needs_title_localization("無法提取標題"))
        self.assertFalse(needs_title_localization("無法下載該網頁的內容。"))
        self.assertFalse(needs_title_localization(""))
        self.assertFalse(needs_title_localization("YouTube"))

    def test_localize_title_chinese_skipped(self):
        title = "【老高與小茉】五大歷史謎團"
        # Should return as-is immediately without LLM call
        self.assertEqual(localize_title(title), title)

    def test_localize_title_foreign_success(self):
        from unittest.mock import patch
        foreign_title = "¿Quién ha sido el más RICO de la historia?"
        with patch("app.services.llm.call_llm_with_fallback", return_value="歷史上誰最富有？"):
            result = localize_title(foreign_title)
            self.assertEqual(result, "歷史上誰最富有？ (¿Quién ha sido el más RICO de la historia?)")

    def test_localize_title_llm_failure_graceful_fallback(self):
        from unittest.mock import patch
        foreign_title = "The History of Rome"
        with patch("app.services.llm.call_llm_with_fallback", side_effect=Exception("API Error")):
            result = localize_title(foreign_title)
            self.assertEqual(result, foreign_title)

    def test_convert_document_to_markdown_needs_ocr_pdf(self):
        import types
        from unittest.mock import patch

        class FakeNeedsOcrError(Exception):
            pass

        fake_anydoc = types.SimpleNamespace(
            NeedsOcrError=FakeNeedsOcrError,
            to_markdown=lambda _path: (_ for _ in ()).throw(FakeNeedsOcrError("pages 1-2 need OCR")),
        )
        fake_info = {
            "group": "document",
            "label": "pdf",
            "description": "PDF document",
            "is_text": False,
            "extensions": ["pdf"],
            "mime_type": "application/pdf",
        }
        with patch("app.services.content.detect_file_type", return_value=fake_info), \
             patch.dict("sys.modules", {"anydoc": fake_anydoc}):
            with self.assertRaises(ValueError) as ctx:
                convert_document_to_markdown("scanned.pdf")
            self.assertIn("掃描影像檔", str(ctx.exception))

    def test_is_valid_raw_title(self):
        self.assertTrue(is_valid_raw_title("How Nvidia Built an AI Empire"))
        self.assertTrue(is_valid_raw_title("英伟达最新财报深度解析"))
        self.assertTrue(is_valid_raw_title("輝達財報背後的三個關鍵訊號"))
        self.assertFalse(is_valid_raw_title(None))
        self.assertFalse(is_valid_raw_title(""))
        self.assertFalse(is_valid_raw_title("A"))
        self.assertFalse(is_valid_raw_title("影片"))
        self.assertFalse(is_valid_raw_title("無法提取標題"))
        self.assertFalse(is_valid_raw_title("無法下載該網頁的內容。"))
        self.assertFalse(is_valid_raw_title("抓取過程中發生錯誤。"))
        self.assertFalse(is_valid_raw_title("短文之摘要"))
        self.assertFalse(is_valid_raw_title("Text Summary"))
        self.assertFalse(is_valid_raw_title("YouTube"))
        self.assertFalse(is_valid_raw_title("X"))

    def test_extract_title_from_summary_variants(self):
        # Standard TITLE: with --- separator
        title, body = extract_title_from_summary("TITLE: 輝達差點沒有黃仁勳？揭開 AI 帝國內幕\n---\n### ⓵ 【容易懂】\n內容正文")
        self.assertEqual(title, "輝達差點沒有黃仁勳？揭開 AI 帝國內幕")
        self.assertTrue(body.startswith("### ⓵ 【容易懂】"))

        # Leading blank lines, fullwidth colon, markdown bold & quotes
        title2, body2 = extract_title_from_summary('\n\n**TITLE：** 「📌 **AI 算力戰爭的下一站**」\n\n正文開始\n---\n第二段')
        self.assertEqual(title2, "AI 算力戰爭的下一站")
        self.assertEqual(body2, "正文開始\n---\n第二段")

        # Heading prefix and Chinese label variants
        title3, body3 = extract_title_from_summary("## SEO標題：《為什麼工程師都在學 Rust？》\n\n第一段")
        self.assertEqual(title3, "為什麼工程師都在學 Rust？")
        self.assertEqual(body3, "第一段")

        title4, body4 = extract_title_from_summary("# title: Why Small Models Win in 2026\nBody text")
        self.assertEqual(title4, "Why Small Models Win in 2026")
        self.assertEqual(body4, "Body text")

    def test_extract_title_from_summary_rejects_missing_or_invalid(self):
        # No TITLE line -> unchanged
        raw = "### ⓵ 【容易懂】\n這是一段沒有標題行的摘要\n\nTITLE: 第四行後不應被拔除"
        # First 3 non-empty lines don't have TITLE: (lines: 1=###, 2=這是..., 3=TITLE:...)
        # Actually line 3 IS the 3rd non-empty line, so put it as 4th non-empty line to verify limit
        raw_four = "### ⓵ 【容易懂】\n第一句\n第二句\nTITLE: 第四行後不應被拔除"
        title, body = extract_title_from_summary(raw_four)
        self.assertIsNone(title)
        self.assertEqual(body, raw_four)

        # Error messages must not be treated as title, and invalid TITLE line is stripped from non-empty body
        err_text = "TITLE: ⚠️ 摘要生成失敗\n內文"
        t_err, b_err = extract_title_from_summary(err_text)
        self.assertIsNone(t_err)
        self.assertEqual(b_err, "內文")

        err_text2 = "TITLE: ❌ 模型無回應\n內文"
        self.assertEqual(extract_title_from_summary(err_text2), (None, "內文"))

        err_text3 = "TITLE: Unknown error occurred\n內文"
        self.assertEqual(extract_title_from_summary(err_text3), (None, "內文"))

        # Too long (>120 chars)
        long_title_text = "TITLE: " + ("超長標題" * 35) + "\n內文"
        self.assertEqual(extract_title_from_summary(long_title_text), (None, "內文"))

    def test_compose_summary_with_source(self):
        # URL + distinct raw_title
        out1 = compose_summary_with_source(
            "輝達差點沒有黃仁勳？",
            "摘要內文",
            original_url="https://youtube.com/watch?v=123",
            raw_title="How Nvidia Almost Died",
        )
        self.assertEqual(
            out1,
            "📌 輝達差點沒有黃仁勳？\n\n摘要內文\n\n🏷️ 原始標題：How Nvidia Almost Died\n▶ https://youtube.com/watch?v=123",
        )

        # URL + identical raw_title -> no duplicate raw title line
        out2 = compose_summary_with_source(
            "相同標題測試",
            "摘要內文",
            original_url="https://example.com/post",
            raw_title="相同標題測試",
        )
        self.assertEqual(out2, "📌 相同標題測試\n\n摘要內文\n\n▶ https://example.com/post")

        # URL + invalid placeholder raw_title -> omit raw title line
        out3 = compose_summary_with_source(
            "SEO 優化後標題",
            "摘要內文",
            original_url="https://example.com/404",
            raw_title="無法下載該網頁的內容。",
        )
        self.assertEqual(out3, "📌 SEO 優化後標題\n\n摘要內文\n\n▶ https://example.com/404")

        # Non-URL short text without raw_title
        out4 = compose_summary_with_source("短文核心洞察", "摘要內文")
        self.assertEqual(out4, "📌 短文核心洞察\n\n摘要內文")

        # Non-URL file with distinct filename raw_title
        out5 = compose_summary_with_source("Q3 財報關鍵解讀", "摘要內文", raw_title="q3_report.pdf")
        self.assertEqual(out5, "📌 Q3 財報關鍵解讀\n\n摘要內文\n\n🏷️ 原始標題：q3_report.pdf")

        # Multi-line raw title and title should be sanitized
        out6 = compose_summary_with_source(
            "第一行\n第二行",
            "摘要內文",
            original_url="https://example.com",
            raw_title="Raw\n\tTitle\x00Here",
        )
        self.assertEqual(
            out6,
            "📌 第一行 第二行\n\n摘要內文\n\n🏷️ 原始標題：Raw Title Here\n▶ https://example.com",
        )

    def test_sanitize_raw_title(self):
        self.assertEqual(sanitize_raw_title("  Hello\n\r\tWorld\x07  "), "Hello World")
        self.assertEqual(sanitize_raw_title(None), "")
        self.assertEqual(len(sanitize_raw_title("A" * 250, max_length=200)), 200)

    def test_is_summary_error_message(self):
        self.assertTrue(is_summary_error_message(None))
        self.assertTrue(is_summary_error_message(""))
        self.assertTrue(is_summary_error_message("   \n  "))
        self.assertTrue(is_summary_error_message("⚠️ 摘要生成失敗：所有 AI 模型服務暫時無法回應"))
        self.assertTrue(is_summary_error_message("Unknown error! Please contact the owner."))
        self.assertFalse(is_summary_error_message("### ⓵ 【容易懂】\n這是正常摘要內容。"))

    def test_split_markdown_safely(self):
        self.assertEqual(_split_markdown_safely(""), [])
        self.assertEqual(_split_markdown_safely("短文", limit=100), ["短文"])

        para1 = "第一段內容。" * 40
        para2 = "第二段內容。" * 40
        para3 = "第三段內容。" * 40
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = _split_markdown_safely(text, limit=300)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 300)
            self.assertTrue(chunk.strip())

        # Hard-split continuous string with no boundaries
        solid = "X" * 750
        solid_chunks = _split_markdown_safely(solid, limit=300)
        self.assertEqual([len(c) for c in solid_chunks], [300, 300, 150])

    def test_extract_title_only_first_line_and_invalid_stripped(self):
        # Line 2 has 標題：, line 1 does not -> must NOT extract line 2
        body_with_line2 = "### ⓵ 【容易懂】\n標題：這不是主標題\n內容繼續"
        self.assertEqual(extract_title_from_summary(body_with_line2), (None, body_with_line2))

        # Paired __ and * markers cleaned
        t1, b1 = extract_title_from_summary("TITLE: __*為什麼小模型正在贏*__\n\n正文內容")
        self.assertEqual(t1, "為什麼小模型正在贏")
        self.assertEqual(b1, "正文內容")

        # Invalid TITLE line on line 1 with valid body -> strip leaked TITLE line
        t2, b2 = extract_title_from_summary("TITLE: ⚠️ 模型錯誤\n---\n正常摘要內文")
        self.assertIsNone(t2)
        self.assertEqual(b2, "正常摘要內文")

        t3, b3 = extract_title_from_summary("TITLE:   \n\n正常摘要內文")
        self.assertIsNone(t3)
        self.assertEqual(b3, "正常摘要內文")

    def test_extract_title_only_title_no_body(self):
        only_title = "TITLE: 只有一行標題卻沒有摘要內文"
        self.assertEqual(extract_title_from_summary(only_title), (None, only_title))

    def test_resolve_final_title(self):
        self.assertEqual(resolve_final_title("AI\n優化標題", "Raw Title"), "AI 優化標題")
        # Valid raw title fallback returns sanitized raw title directly without LLM call
        self.assertEqual(resolve_final_title(None, "How\nNvidia Won"), "How Nvidia Won")
        # Invalid/placeholder raw title must return default_title
        self.assertEqual(resolve_final_title(None, "無法下載該網頁的內容。", default_title="短文之摘要"), "短文之摘要")
        self.assertEqual(resolve_final_title(None, "影片", default_title="Text Summary"), "Text Summary")

    def test_prepare_wiki_content_demotes_h1_and_appends_source(self):
        summary = (
            "# 摘要開頭一級標題\n"
            "第一段說明\n\n"
            "### ⓶ 【總結】\n"
            "重點整理\n\n"
            "✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡"
        )
        wiki_md = prepare_wiki_content(
            title="輝達帝國背後的秘密",
            summary=summary,
            original_url="https://youtube.com/watch?v=abc",
            raw_title="Nvidia Secrets",
        )
        lines = wiki_md.splitlines()
        self.assertEqual(lines[0], "# 輝達帝國背後的秘密")
        self.assertIn("## 摘要開頭一級標題", wiki_md)
        self.assertNotIn("\n# 摘要開頭一級標題", wiki_md)
        self.assertNotIn("Oli小濃縮 Summary bot", wiki_md)
        self.assertIn("🏷️ 原始標題：Nvidia Secrets", wiki_md)
        self.assertIn("▶ 原始連結：https://youtube.com/watch?v=abc", wiki_md)


if __name__ == "__main__":
    unittest.main()

