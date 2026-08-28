import unittest
from unittest.mock import patch, MagicMock
from app.services.wiki import (
    publish_wiki_page,
    append_wiki_page,
    read_wiki_page,
    generate_wiki_slug,
    sanitize_wiki_markdown,
    render_markdown,
    parse_web_to_markdown,
    lint_markdown,
)


class TestWikiService(unittest.TestCase):
    def test_generate_wiki_slug(self):
        slug = generate_wiki_slug("AI 摘要報告 2026")
        self.assertTrue(slug.startswith("AI-摘要報告-2026"))
        self.assertIn("-", slug)

    def test_sanitize_wiki_markdown_strips_preamble(self):
        messy_input = "好的，這是我為您整理的報告：\n\n# 2026 全球趨勢報告\n\n內容段落..."
        sanitized = sanitize_wiki_markdown(messy_input)
        self.assertTrue(sanitized.startswith("# 2026 全球趨勢報告"))

    def test_sanitize_wiki_markdown_adds_title_if_missing(self):
        raw_text = "直接開始內容沒有標題"
        sanitized = sanitize_wiki_markdown(raw_text, title="自訂報告標題")
        self.assertTrue(sanitized.startswith("# 自訂報告標題"))

    @patch("app.services.wiki.requests.post")
    def test_publish_wiki_page_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "err": 0,
            "msg": "ok",
            "data": {
                "url": "https://wiki.david888.com/my-note",
                "shareUrl": "https://wiki.david888.com/share/abc1234"
            }
        }
        mock_post.return_value = mock_resp

        res = publish_wiki_page("Markdown Content", title="Test Title", theme="tokyo-night")
        self.assertTrue(res["success"])
        self.assertEqual(res["shareUrl"], "https://wiki.david888.com/share/abc1234")
        self.assertEqual(res["presentUrl"], "https://wiki.david888.com/share/abc1234/present")
        self.assertEqual(res["bookUrl"], "https://wiki.david888.com/share/abc1234/book")

    @patch("app.services.wiki.requests.post")
    def test_publish_wiki_page_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {
            "err": 1,
            "msg": "Invalid token or password"
        }
        mock_post.return_value = mock_resp

        res = publish_wiki_page("Content", title="Error Note")
        self.assertFalse(res["success"])
        self.assertIn("Invalid token", res["error"])

    @patch("app.services.wiki.requests.post")
    def test_append_wiki_page_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "err": 0,
            "msg": "ok",
            "data": {
                "url": "https://wiki.david888.com/my-note",
                "shareUrl": "https://wiki.david888.com/share/abc1234"
            }
        }
        mock_post.return_value = mock_resp

        res = append_wiki_page("my-note", "Appended text")
        self.assertTrue(res["success"])
        self.assertEqual(res["shareUrl"], "https://wiki.david888.com/share/abc1234")

    @patch("app.services.wiki.requests.get")
    def test_read_wiki_page_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "# Wiki Title\nContent"
        mock_get.return_value = mock_resp

        res = read_wiki_page("my-note")
        self.assertTrue(res["success"])
        self.assertIn("Wiki Title", res["content"])

    @patch("app.services.wiki.requests.post")
    def test_render_markdown(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"err": 0, "data": {"html": "<p>test</p>"}}
        mock_post.return_value = mock_resp
        res = render_markdown("# Test")
        self.assertTrue(res["success"])
        self.assertEqual(res["html"], "<p>test</p>")

    @patch("app.services.wiki.requests.post")
    def test_lint_markdown(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"err": 0, "data": {"valid": True, "issues": [], "fixedMarkdown": "# Fixed"}}
        mock_post.return_value = mock_resp
        res = lint_markdown("# Test")
        self.assertTrue(res["success"])
        self.assertTrue(res["valid"])


if __name__ == "__main__":
    unittest.main()
