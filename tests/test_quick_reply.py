import unittest
from app.services.quick_reply import (
    get_summary_quick_reply_keyboard,
    detect_quick_reply_intent,
    build_transform_prompt,
    build_concept_image_url
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

    def test_build_concept_image_url(self):
        url = build_concept_image_url("futuristic cyberpunk data visualization neural net")
        self.assertTrue(url.startswith("https://image.pollinations.ai/prompt/"))
        self.assertIn("model=flux", url)
        self.assertIn("cyberpunk", url)


if __name__ == "__main__":
    unittest.main()
