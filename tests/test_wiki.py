import unittest
from unittest.mock import patch, MagicMock
from app.services.wiki import publish_wiki_page, append_wiki_page, read_wiki_page, generate_wiki_slug


class TestWikiService(unittest.TestCase):
    def test_generate_wiki_slug(self):
        slug = generate_wiki_slug("AI 摘要報告 2026")
        self.assertTrue(slug.startswith("AI-摘要報告-2026"))
        self.assertIn("-", slug)

    @patch("app.services.wiki.requests.post")
    def test_publish_wiki_page_success(self, mock_post):
        mock_resp = MagicMock()
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

    @patch("app.services.wiki.requests.post")
    def test_publish_wiki_page_error(self, mock_post):
        mock_resp = MagicMock()
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


if __name__ == "__main__":
    unittest.main()
