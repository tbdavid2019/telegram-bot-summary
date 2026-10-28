import unittest
from unittest.mock import patch, MagicMock
import json

from app.services.podcast import (
    is_pocketcasts_url,
    resolve_pocketcasts_url,
    extract_pocketcasts_episode,
    get_pocketcasts_title,
)
from app.legacy import process_pocketcasts_url, get_web_title


class TestPodcastService(unittest.TestCase):
    def setUp(self):
        # Clear lru_cache between tests
        extract_pocketcasts_episode.cache_clear()

    def test_is_pocketcasts_url(self):
        self.assertTrue(is_pocketcasts_url("https://pca.st/9wirf5m8"))
        self.assertTrue(is_pocketcasts_url("http://pca.st/9wirf5m8"))
        self.assertTrue(is_pocketcasts_url("https://pocketcasts.com/podcast/test/2d1c2ae0-1136-0137-f265-1d245fc5f9cf"))
        self.assertTrue(is_pocketcasts_url("https://play.pocketcasts.com/podcasts/2d1c2ae0-1136-0137-f265-1d245fc5f9cf/d0feb37e-810c-4c47-b334-c0aff47ef822"))
        self.assertTrue(is_pocketcasts_url("pca.st/9wirf5m8"))

        self.assertFalse(is_pocketcasts_url("https://youtube.com/watch?v=123"))
        self.assertFalse(is_pocketcasts_url("https://soundcloud.com/test/track"))
        self.assertFalse(is_pocketcasts_url("https://notpocketcasts.com"))
        self.assertFalse(is_pocketcasts_url(""))
        self.assertFalse(is_pocketcasts_url(None))

    @patch("requests.head")
    def test_resolve_pocketcasts_url_shortlink_head(self, mock_head):
        target_location = "https://pocketcasts.com/podcast/show/2d1c2ae0-1136-0137-f265-1d245fc5f9cf/ep/d0feb37e-810c-4c47-b334-c0aff47ef822"
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"Location": target_location}
        mock_head.return_value = mock_resp

        resolved = resolve_pocketcasts_url("https://pca.st/9wirf5m8")
        self.assertEqual(resolved, target_location)
        mock_head.assert_called_once()

    @patch("requests.head", side_effect=Exception("HEAD failed"))
    @patch("requests.get")
    def test_resolve_pocketcasts_url_fallback_to_get(self, mock_get, mock_head):
        target_location = "https://pocketcasts.com/podcast/show/2d1c2ae0-1136-0137-f265-1d245fc5f9cf"
        mock_resp = MagicMock()
        mock_resp.status_code = 302
        mock_resp.headers = {"Location": target_location}
        mock_get.return_value = mock_resp

        resolved = resolve_pocketcasts_url("https://pca.st/9wirf5m8")
        self.assertEqual(resolved, target_location)
        mock_get.assert_called_once()

    def test_resolve_pocketcasts_url_non_pcast(self):
        url = "https://pocketcasts.com/podcast/already-resolved"
        self.assertEqual(resolve_pocketcasts_url(url), url)

    def test_resolve_pocketcasts_url_ssrf_blocked(self):
        unsafe_url = "http://127.0.0.1/pca.st/fake"
        self.assertEqual(resolve_pocketcasts_url(unsafe_url), unsafe_url)

    @patch("requests.get")
    def test_extract_pocketcasts_episode_specific_match(self, mock_get):
        podcast_uuid = "2d1c2ae0-1136-0137-f265-1d245fc5f9cf"
        episode_uuid = "d0feb37e-810c-4c47-b334-c0aff47ef822"
        full_url = f"https://pocketcasts.com/podcast/show/{podcast_uuid}/ep/{episode_uuid}"

        api_payload = {
            "podcast": {
                "title": "大人的Small Talk",
                "episodes": [
                    {
                        "uuid": "different-uuid-1111-2222-333344445555",
                        "title": "最新一集",
                        "url": "https://cdn.podcast.com/ep2.mp3",
                        "duration": 1800,
                        "published": "2026-10-26T00:00:00Z"
                    },
                    {
                        "uuid": episode_uuid,
                        "title": "EP718 你在財富階梯的哪一階",
                        "url": "https://cdn.podcast.com/ep718.mp3",
                        "duration": 2494,
                        "published": "2026-10-25T20:30:00Z"
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_payload
        mock_get.return_value = mock_resp

        ep_info = extract_pocketcasts_episode(full_url)
        self.assertIsNotNone(ep_info)
        self.assertEqual(ep_info["podcast_title"], "大人的Small Talk")
        self.assertEqual(ep_info["episode_title"], "EP718 你在財富階梯的哪一階")
        self.assertEqual(ep_info["audio_url"], "https://cdn.podcast.com/ep718.mp3")
        self.assertEqual(ep_info["duration"], 2494)
        self.assertEqual(ep_info["episode_uuid"], episode_uuid)

    @patch("requests.get")
    def test_extract_pocketcasts_episode_latest_default(self, mock_get):
        podcast_uuid = "2d1c2ae0-1136-0137-f265-1d245fc5f9cf"
        channel_url = f"https://pocketcasts.com/podcast/show/{podcast_uuid}"

        api_payload = {
            "podcast": {
                "title": "測試 Podcast",
                "episodes": [
                    {
                        "uuid": "latest-ep-uuid",
                        "title": "最新集數標題",
                        "url": "https://cdn.podcast.com/latest.mp3",
                        "duration": 1200,
                        "published": "2026-10-28T00:00:00Z"
                    }
                ]
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = api_payload
        mock_get.return_value = mock_resp

        ep_info = extract_pocketcasts_episode(channel_url)
        self.assertIsNotNone(ep_info)
        self.assertEqual(ep_info["episode_title"], "最新集數標題")
        self.assertEqual(ep_info["audio_url"], "https://cdn.podcast.com/latest.mp3")

    @patch("requests.get")
    def test_extract_pocketcasts_episode_lru_cache(self, mock_get):
        podcast_uuid = "2d1c2ae0-1136-0137-f265-1d245fc5f9cf"
        url = f"https://pocketcasts.com/podcast/show/{podcast_uuid}"

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "podcast": {
                "title": "Cache Test",
                "episodes": [{"uuid": "1", "title": "Ep 1", "url": "https://cdn.test/1.mp3"}]
            }
        }
        mock_get.return_value = mock_resp

        res1 = extract_pocketcasts_episode(url)
        res2 = extract_pocketcasts_episode(url)

        self.assertEqual(res1, res2)
        # Should only call API once due to lru_cache
        self.assertEqual(mock_get.call_count, 1)

    def test_extract_pocketcasts_ssrf_blocked(self):
        unsafe_url = "http://169.254.169.254/pocketcasts.com"
        self.assertIsNone(extract_pocketcasts_episode(unsafe_url))

    @patch("app.services.podcast.extract_pocketcasts_episode")
    def test_get_pocketcasts_title(self, mock_extract):
        mock_extract.return_value = {
            "podcast_title": "大人的Small Talk",
            "episode_title": "EP718 你在財富階梯的哪一階",
        }
        title = get_pocketcasts_title("https://pca.st/9wirf5m8")
        self.assertEqual(title, "EP718 你在財富階梯的哪一階 - 大人的Small Talk")

        # When title already contains podcast title
        mock_extract.return_value = {
            "podcast_title": "大人學",
            "episode_title": "大人學 EP718",
        }
        title2 = get_pocketcasts_title("https://pca.st/9wirf5m8")
        self.assertEqual(title2, "大人學 EP718")

    @patch("app.legacy.download_and_transcribe_podcast", return_value=["轉錄第1段", "轉錄第2段"])
    @patch("app.legacy.extract_pocketcasts_episode")
    def test_process_pocketcasts_url_success(self, mock_extract, mock_download):
        mock_extract.return_value = {
            "podcast_title": "大人的Small Talk",
            "episode_title": "EP718",
            "audio_url": "https://cdn.test/ep718.mp3",
        }

        chunks = process_pocketcasts_url("https://pca.st/9wirf5m8")
        self.assertEqual(chunks, ["轉錄第1段", "轉錄第2段"])
        mock_download.assert_called_once_with("https://cdn.test/ep718.mp3")

    def test_process_pocketcasts_url_ssrf_blocked(self):
        res = process_pocketcasts_url("http://127.0.0.1/pca.st/123")
        self.assertEqual(res, ["不支援或受保護的私有/內部網路網址。"])

    @patch("app.legacy.get_pocketcasts_title", return_value="EP718 - 大人的Small Talk")
    def test_get_web_title_pocketcasts(self, mock_get_title):
        title = get_web_title("https://pca.st/9wirf5m8")
        self.assertEqual(title, "EP718 - 大人的Small Talk")
        mock_get_title.assert_called_once_with("https://pca.st/9wirf5m8")


if __name__ == "__main__":
    unittest.main()
