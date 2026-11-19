import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.telegram_delivery import format_for_telegram, send_telegram_formatted


class TestTelegramDelivery(unittest.IsolatedAsyncioTestCase):
    def test_format_for_telegram_empty_inputs(self):
        self.assertEqual(format_for_telegram(""), "")
        self.assertIsNone(format_for_telegram(None))

    async def test_send_telegram_formatted_skips_empty_text(self):
        bot = MagicMock()
        bot.send_message = AsyncMock()
        await send_telegram_formatted(bot, 123, "")
        await send_telegram_formatted(bot, 123, "   \n  ")
        bot.send_message.assert_not_called()

    async def test_send_telegram_formatted_per_chunk_fallback_does_not_resend_prior_chunks(self):
        bot = MagicMock()
        calls = []

        async def fake_send_message(**kwargs):
            calls.append(kwargs)
            # Fail ONLY when chunk 2 is sent with parse_mode='HTML'
            if kwargs.get("parse_mode") == "HTML" and "第二塊" in kwargs.get("text", ""):
                raise Exception("Bad Request: can't parse entities")

        bot.send_message = AsyncMock(side_effect=fake_send_message)
        markup = object()

        chunk1_text = "第一塊內容。" * 350  # ~2100 chars
        chunk2_text = "第二塊內容。" * 350  # ~2100 chars -> combined > 3200 so split into 2 chunks
        raw_text = f"{chunk1_text}\n\n{chunk2_text}"

        with patch("app.services.telegram_delivery.format_for_telegram", side_effect=lambda s: f"<b>{s}</b>"):
            await send_telegram_formatted(bot, 999, raw_text, reply_markup=markup)

        # Expect exactly 3 calls:
        # 1. Chunk 1 HTML (succeeds, no reply_markup)
        # 2. Chunk 2 HTML (raises)
        # 3. Chunk 2 plain text fallback (succeeds, carries reply_markup)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["parse_mode"], "HTML")
        self.assertIn("第一塊內容", calls[0]["text"])
        self.assertIsNone(calls[0]["reply_markup"])

        self.assertEqual(calls[1]["parse_mode"], "HTML")
        self.assertIn("第二塊內容", calls[1]["text"])

        self.assertNotIn("parse_mode", calls[2])
        self.assertIn("第二塊內容", calls[2]["text"])
        self.assertIs(calls[2]["reply_markup"], markup)

    async def test_send_telegram_formatted_over_4000_html_falls_back_for_that_chunk_only(self):
        bot = MagicMock()
        calls = []

        async def fake_send_message(**kwargs):
            calls.append(kwargs)

        bot.send_message = AsyncMock(side_effect=fake_send_message)
        markup = object()
        raw_text = "短段落內容"

        # Simulate HTML expansion pushing formatted chunk over Telegram's 4000-char limit
        with patch("app.services.telegram_delivery.format_for_telegram", return_value="<b>" + ("A" * 4050) + "</b>"):
            await send_telegram_formatted(bot, 888, raw_text, reply_markup=markup)

        self.assertEqual(len(calls), 1)
        self.assertNotIn("parse_mode", calls[0])
        self.assertEqual(calls[0]["text"], raw_text)
        self.assertIs(calls[0]["reply_markup"], markup)


if __name__ == "__main__":
    unittest.main()
