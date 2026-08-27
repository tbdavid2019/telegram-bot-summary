import unittest
from unittest.mock import patch, MagicMock
from app.services.box import upload_file_to_box, upload_url_to_box, get_box_stats


class TestBoxService(unittest.TestCase):
    @patch("app.services.box.requests.post")
    def test_upload_file_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": "success",
            "data": {
                "id": "100",
                "url": "https://d36gp3xejpe77o.cloudfront.net/storage/file/test.txt",
                "share_url": "https://box.david888.com/v/abcd"
            }
        }
        mock_post.return_value = mock_resp

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello box")
            tmp_name = f.name

        res = upload_file_to_box(tmp_name, title="Test", description="Desc")
        self.assertTrue(res["success"])
        self.assertEqual(res["id"], "100")
        self.assertIn("cloudfront.net", res["url"])
        self.assertIn("box.david888.com", res["share_url"])

    @patch("app.services.box.requests.post")
    def test_upload_url_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": "success",
            "data": {
                "id": "101",
                "url": "https://d36gp3xejpe77o.cloudfront.net/storage/video/test.mp4",
                "share_url": "https://box.david888.com/v/efgh"
            }
        }
        mock_post.return_value = mock_resp

        res = upload_url_to_box("https://example.com/test.mp4", title="Video")
        self.assertTrue(res["success"])
        self.assertEqual(res["id"], "101")
        self.assertIn("cloudfront.net", res["url"])

    @patch("app.services.box.requests.get")
    def test_get_box_stats_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "result": "success",
            "data": {"total": 50, "video": 10, "file": 5}
        }
        mock_get.return_value = mock_resp

        res = get_box_stats()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["total"], 50)

    @patch("app.services.box.requests.post")
    def test_upload_url_fallback(self, mock_post):
        # First call fails, second call succeeds
        mock_fail = MagicMock()
        mock_fail.json.return_value = {"result": "error", "message": "Primary down"}
        mock_success = MagicMock()
        mock_success.json.return_value = {
            "result": "success",
            "data": {
                "id": "102",
                "url": "https://d36gp3xejpe77o.cloudfront.net/storage/audio/test.mp3",
                "share_url": "https://box.glsoft.ai/v/fallback"
            }
        }
        mock_post.side_effect = [mock_fail, mock_success]

        res = upload_url_to_box("https://example.com/audio.mp3", title="Audio")
        self.assertTrue(res["success"])
        self.assertEqual(res["id"], "102")
        self.assertEqual(res["endpoint"], "https://box.glsoft.ai")


if __name__ == "__main__":
    unittest.main()
