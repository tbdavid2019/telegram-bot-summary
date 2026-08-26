import unittest
from unittest.mock import patch, MagicMock

from app.services.divination import (
    parse_tarot_command,
    parse_yinyuan_command,
    format_tarot_reply,
    format_yinyuan_reply,
    ask_tarot_api,
    ask_yinyuan_api,
)


class DivinationTests(unittest.TestCase):
    def test_parse_tarot_command_default_spread(self):
        spread, question = parse_tarot_command("最近適合轉職嗎？")
        self.assertEqual("three", spread)
        self.assertEqual("最近適合轉職嗎？", question)

    def test_parse_tarot_command_with_spread(self):
        spread, question = parse_tarot_command("single 今日運勢如何？")
        self.assertEqual("single", spread)
        self.assertEqual("今日運勢如何？", question)

    def test_parse_tarot_command_chinese_alias(self):
        spread, question = parse_tarot_command("單張 今天財運")
        self.assertEqual("single", spread)
        self.assertEqual("今天財運", question)

    def test_parse_tarot_command_empty(self):
        spread, question = parse_tarot_command("")
        self.assertEqual("three", spread)
        self.assertEqual("", question)

    def test_parse_yinyuan_command_fortune_default(self):
        mode, question, y1, y2 = parse_yinyuan_command("我和對方適合在一起嗎？")
        self.assertEqual("fortune", mode)
        self.assertEqual("我和對方適合在一起嗎？", question)
        self.assertIsNone(y1)
        self.assertIsNone(y2)

    def test_parse_yinyuan_command_zodiac_mode(self):
        mode, question, y1, y2 = parse_yinyuan_command("zodiac 1995 1998 我們合嗎？")
        self.assertEqual("zodiac", mode)
        self.assertEqual("我們合嗎？", question)
        self.assertEqual(1995, y1)
        self.assertEqual(1998, y2)

    def test_parse_yinyuan_command_zodiac_chinese_keyword(self):
        mode, question, y1, y2 = parse_yinyuan_command("生肖 1992 1996")
        self.assertEqual("zodiac", mode)
        self.assertEqual(1992, y1)
        self.assertEqual(1996, y2)
        self.assertIn("1992", question)

    def test_format_tarot_reply_success(self):
        data = {
            "success": True,
            "question": "測試工作運",
            "reading": {
                "spread": "three",
                "cards": [
                    {"position": "過去", "name": "愚者", "orientation": "正位", "isMajor": True},
                    {"position": "現在", "name": "聖杯二", "orientation": "正位", "isMajor": False},
                    {"position": "未來", "name": "太陽", "orientation": "逆位", "isMajor": True},
                ],
            },
            "answer": "這是 AI 占卜解讀建議。",
        }
        reply = format_tarot_reply(data)
        self.assertIn("【塔羅占卜 Tarot Reading】", reply)
        self.assertIn("測試工作運", reply)
        self.assertIn("愚者（正位） ✨(大阿爾克那)", reply)
        self.assertIn("聖杯二（正位）", reply)
        self.assertIn("這是 AI 占卜解讀建議。", reply)

    def test_format_tarot_reply_error(self):
        data = {"success": False, "message": "後端服務錯誤"}
        reply = format_tarot_reply(data)
        self.assertIn("❌ 塔羅占卜失敗：後端服務錯誤", reply)

    def test_format_yinyuan_reply_fortune(self):
        data = {
            "success": True,
            "question": "感情求籤",
            "result": {
                "number": 1,
                "title": "上上籤",
                "poem": "花開月滿，緣分宜以真誠相待。",
            },
            "answer": "這是月老籤詩 AI 解讀。",
        }
        reply = format_yinyuan_reply(data, mode="fortune")
        self.assertIn("【月老姻緣籤詩】", reply)
        self.assertIn("第 1 籤 【上上籤】", reply)
        self.assertIn("花開月滿", reply)
        self.assertIn("這是月老籤詩 AI 解讀。", reply)

    def test_format_yinyuan_reply_zodiac(self):
        data = {
            "success": True,
            "question": "生肖合婚",
            "result": {
                "first": {"year": 1995, "zodiac": "豬"},
                "second": {"year": 1998, "zodiac": "虎"},
                "relationship": "六合：互相扶持、容易建立默契",
                "score": 88,
            },
            "answer": "這是生肖合婚 AI 建議。",
        }
        reply = format_yinyuan_reply(data, mode="zodiac")
        self.assertIn("【月老生肖合婚測算】", reply)
        self.assertIn("1995 年生（生肖屬 豬）", reply)
        self.assertIn("1998 年生（生肖屬 虎）", reply)
        self.assertIn("88 分", reply)
        self.assertIn("這是生肖合婚 AI 建議。", reply)

    @patch("requests.post")
    def test_ask_tarot_api_calls_endpoint(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": True}
        mock_post.return_value = mock_resp

        result = ask_tarot_api("運勢", spread="single", base_url="https://qi.david888.com")
        self.assertTrue(result["success"])
        mock_post.assert_called_once_with(
            "https://qi.david888.com/api/tarot-question",
            json={"question": "運勢", "spread": "single"},
            timeout=60.0,
        )

    @patch("requests.post")
    def test_ask_yinyuan_api_calls_endpoint(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"success": True}
        mock_post.return_value = mock_resp

        result = ask_yinyuan_api("合婚", mode="zodiac", first_year=1990, second_year=1995, base_url="https://qi.david888.com")
        self.assertTrue(result["success"])
        mock_post.assert_called_once_with(
            "https://qi.david888.com/api/yinyuan-question",
            json={"question": "合婚", "mode": "zodiac", "firstYear": 1990, "secondYear": 1995},
            timeout=60.0,
        )
