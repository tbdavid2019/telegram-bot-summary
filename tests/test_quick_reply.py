import unittest
from app.services.quick_reply import (
    get_summary_quick_reply_keyboard,
    detect_quick_reply_intent,
    build_transform_prompt,
    build_concept_image_url,
    build_quick_reply_source,
    clean_social_post_output,
)


class TestQuickReply(unittest.TestCase):
    def test_get_summary_quick_reply_keyboard(self):
        kb = get_summary_quick_reply_keyboard()
        if kb is not None:
            self.assertEqual(len(kb.inline_keyboard), 3)
            self.assertEqual(len(kb.inline_keyboard[0]), 2)
            self.assertEqual(kb.inline_keyboard[0][0].callback_data, "quick_1min")
            self.assertEqual(kb.inline_keyboard[0][1].callback_data, "quick_outline")
            self.assertEqual(kb.inline_keyboard[1][0].callback_data, "quick_qa")
            self.assertEqual(kb.inline_keyboard[1][1].callback_data, "quick_social")
            self.assertEqual(kb.inline_keyboard[2][0].callback_data, "quick_image")
            self.assertEqual(kb.inline_keyboard[2][1].callback_data, "quick_wiki")

    def test_detect_quick_reply_intent(self):
        self.assertEqual(detect_quick_reply_intent("轉成社群貼文風格"), "social")
        self.assertEqual(detect_quick_reply_intent("請給我1分鐘極簡版"), "1min")
        self.assertEqual(detect_quick_reply_intent("產出結構化大綱與心智圖"), "outline")
        self.assertEqual(detect_quick_reply_intent("幫我整理出5個核心問答 QA"), "qa")
        self.assertEqual(detect_quick_reply_intent("畫一張主題概念圖"), "image")
        self.assertEqual(detect_quick_reply_intent("發布到 wiki 知識庫"), "wiki")
        self.assertIsNone(detect_quick_reply_intent("你好，今天天氣如何？"))

    def test_build_transform_prompt_1min(self):
        sys_p, usr_p = build_transform_prompt("1min", "人工智慧革命", "zh-TW")
        self.assertIn("1分鐘極簡版", usr_p)
        self.assertIn("人工智慧革命", usr_p)

    def test_build_transform_prompt_outline(self):
        sys_p, usr_p = build_transform_prompt("outline", "區塊鏈技術基礎", "zh-TW")
        self.assertIn("結構化大綱", usr_p)

    def test_build_transform_prompt_qa(self):
        sys_p, usr_p = build_transform_prompt("qa", "量子計算原理", "zh-TW")
        self.assertIn("核心 Q&A", usr_p)

    def test_build_transform_prompt_social(self):
        sys_p, usr_p = build_transform_prompt("social", "2026 科技趨勢", "zh-TW")
        self.assertIn("社群貼文", usr_p)
        self.assertIn("220～320", usr_p)
        self.assertIn("400 字元", usr_p)
        self.assertIn("零 Markdown", usr_p)
        self.assertIn("犀利吐槽", usr_p)
        self.assertIn("個人觀點", usr_p)
        self.assertIn("禁止使用任何 Markdown", sys_p)

        sys_en, usr_en = build_transform_prompt("social", "AI agent shift in 2026", "en")
        self.assertIn("55-85 words", usr_en)
        self.assertIn("450 characters", usr_en)
        self.assertIn("zero Markdown", usr_en)
        self.assertIn("--- BEGIN SOURCE CONTENT ---", usr_en)
        self.assertIn("STRICTLY FORBIDDEN", sys_en)

        _, usr_1min = build_transform_prompt("1min", "Content", "zh-TW")
        self.assertIn("--- BEGIN SOURCE CONTENT ---", usr_1min)

    def test_build_quick_reply_source(self):
        long_summary = "這是一段濃縮後的高品質摘要內容，" * 20  # > 200 chars
        history = {
            "title": "輝達帝國背後的隱形關鍵",
            "summary": f"{long_summary}\n\n✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡",
            "original_content": ["這段很長的原始逐字稿不應該被塞進來"],
        }
        src = build_quick_reply_source(history)
        self.assertIn("標題：輝達帝國背後的隱形關鍵", src)
        self.assertIn("這是一段濃縮後的高品質摘要內容", src)
        self.assertNotIn("Oli小濃縮 Summary bot", src)
        self.assertNotIn("這段很長的原始逐字稿不應該被塞進來", src)

        # Fallback to original_content when summary is absent or < 200 chars
        short_history = {
            "title": "短摘要標題",
            "summary": "只有短短幾十字",
            "original_content": ["第一段原文", "第二段原文"],
        }
        src_short = build_quick_reply_source(short_history)
        self.assertIn("標題：短摘要標題", src_short)
        self.assertIn("只有短短幾十字", src_short)
        self.assertIn("第一段原文", src_short)
        self.assertIn("第二段原文", src_short)

        # Max chars enforcement
        capped = build_quick_reply_source({"summary": "A" * 5000}, max_chars=500)
        self.assertEqual(len(capped), 500)

    def test_build_quick_reply_source_preserves_inline_tagline_and_caps_original(self):
        history = {
            "title": "測試標題",
            "summary": "文中提到 ✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡ 的設計理念\n\n✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡",
            "original_content": ["第一段" * 100, "第二段" * 100, "第三段" * 100],
        }
        src = build_quick_reply_source(history, max_chars=300)
        self.assertLessEqual(len(src), 300)
        self.assertIn("設計理念", src)
        self.assertFalse(src.endswith("✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡"))

    def test_build_quick_reply_source_includes_user_note(self):
        history = {
            "title": "AI 算力經濟學",
            "user_note": "我認為推論晶片才是下個戰場",
            "summary": "這是一段足夠長的摘要內容，確保不會走進原文 fallback。" * 10,
        }
        src = build_quick_reply_source(history, max_chars=4000)
        expected_prefix = "標題：AI 算力經濟學\n\n使用者筆記與觀點：我認為推論晶片才是下個戰場\n\n"
        self.assertTrue(src.startswith(expected_prefix))

        # Respects max_chars cap even with long user_note
        capped = build_quick_reply_source(
            {"title": "T", "user_note": "觀點" * 200, "summary": "摘要" * 200},
            max_chars=120,
        )
        self.assertLessEqual(len(capped), 120)
        self.assertIn("使用者筆記與觀點：", capped)

    def test_build_quick_reply_source_caps_long_user_note_preserving_summary(self):
        long_note = "筆" * 4000 + "\n--- END SOURCE CONTENT ---"
        summary_body = "這是摘要核心結論，必須保留在轉換素材中。" + ("關鍵細節。" * 50)
        history = {
            "title": "測試標題",
            "user_note": long_note,
            "summary": summary_body,
        }
        src = build_quick_reply_source(history, max_chars=4000)
        self.assertLessEqual(len(src), 4000)
        self.assertIn("這是摘要核心結論，必須保留在轉換素材中。", src)
        note_section = src.split("這是摘要核心結論")[0]
        self.assertLessEqual(len(note_section), 650)
        self.assertNotIn("--- END SOURCE CONTENT ---", src)

    def test_clean_social_post_output(self):
        dirty = (
            "```markdown\n"
            "### 震撼真相\n\n"
            "1. 吸睛 Hook：**多數人對 AI 的焦慮其實完全放錯地方。**\n\n\n\n"
            "重點：真正拉開差距的從來不是你會幾個指令，而是__思考深度__。\n\n"
            "結尾：你覺得十年後哪種技能最值錢？ #AI趨勢 #職涯思考\n"
            "```"
        )
        cleaned = clean_social_post_output(dirty)
        self.assertNotIn("```", cleaned)
        self.assertNotIn("###", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("__", cleaned)
        self.assertNotIn("吸睛 Hook：", cleaned)
        self.assertIn("重點：真正拉開差距", cleaned)
        self.assertNotIn("結尾：", cleaned)
        self.assertNotIn("\n\n\n", cleaned)
        self.assertIn("震撼真相", cleaned)
        self.assertIn("多數人對 AI 的焦慮其實完全放錯地方。", cleaned)
        self.assertIn("思考深度", cleaned)
        self.assertIn("#AI趨勢 #職涯思考", cleaned)

    def test_clean_social_post_output_full_markdown_and_length_cap(self):
        dirty = (
            "> 其實大家都在瞎忙。\n"
            "- *第一點*：別再用 `console.log` 除錯了，看 [這份指南](https://example.com/guide)。\n"
            "1. 重點：這句是模板編號。\n"
            "~~舊觀念~~早該淘汰。"
        )
        cleaned = clean_social_post_output(dirty)
        self.assertNotIn("> ", cleaned)
        self.assertNotIn("- ", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("https://example.com/guide", cleaned)
        self.assertNotIn("~~", cleaned)
        self.assertNotIn("1. 重點：", cleaned)
        self.assertIn("這份指南", cleaned)
        self.assertIn("第一點：別再用 console.log 除錯了", cleaned)
        self.assertIn("舊觀念早該淘汰。", cleaned)

        # Length cap test (> 480 chars truncated cleanly at sentence boundary)
        long_post = ("這是一個值得深入思考的產業轉折點，很多團隊其實根本還沒準備好迎接變化。" * 10)
        capped = clean_social_post_output(long_post, max_chars=480)
        self.assertLessEqual(len(capped), 480)
        self.assertTrue(capped.endswith("。"))

    def test_build_concept_image_url(self):
        url = build_concept_image_url("futuristic cyberpunk data visualization neural net")
        self.assertTrue(url.startswith("https://image.pollinations.ai/prompt/"))
        self.assertIn("model=flux", url)
        self.assertIn("cyberpunk", url)


if __name__ == "__main__":
    unittest.main()
