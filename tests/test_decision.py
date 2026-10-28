import unittest
from unittest.mock import patch, MagicMock
import json

from app.services.decision import (
    is_decision_ad_filter_enabled,
    call_clef_systemone,
    is_advertisement_content,
    get_cached_decision,
    store_cached_decision,
    clear_decision_cache,
    PRIMARY_CLEF_URL,
    FALLBACK_CLEF_URL,
)


class TestDecisionService(unittest.TestCase):
    def setUp(self):
        clear_decision_cache()

    def tearDown(self):
        clear_decision_cache()

    def test_is_decision_ad_filter_enabled_default_and_user_pref(self):
        # Default should be enabled
        with patch.dict("os.environ", {}, clear=False):
            self.assertTrue(is_decision_ad_filter_enabled())

        # User pref overrides default
        self.assertFalse(is_decision_ad_filter_enabled(user_pref=False))
        self.assertTrue(is_decision_ad_filter_enabled(user_pref=True))

        # Env var override
        with patch.dict("os.environ", {"DECISION_AD_FILTER_ENABLED": "false"}):
            self.assertFalse(is_decision_ad_filter_enabled())

    @patch("requests.post")
    def test_call_clef_systemone_primary_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "model": "clef-flash",
            "answers": {
                "classification": {
                    "type": "choice",
                    "choice": "ad",
                    "confidence": 0.95,
                    "probabilities": {"ad": 0.96, "normal": 0.04},
                }
            },
        }
        mock_post.return_value = mock_resp

        res = call_clef_systemone("限時特價，加LINE領明牌")
        self.assertTrue(res["success"])
        self.assertTrue(res["is_ad"])
        self.assertEqual(res["choice"], "ad")
        self.assertGreater(res["prob_ad"], 0.90)
        self.assertEqual(res["endpoint_used"], PRIMARY_CLEF_URL)
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_call_clef_systemone_failover_to_fallback(self, mock_post):
        # Primary fails with 500, Fallback succeeds with 200
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        fail_resp.text = "Internal Server Error"

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.json.return_value = {
            "model": "clef-flash-q4_k_m",
            "answers": {
                "classification": {
                    "type": "choice",
                    "choice": "ad",
                    "confidence": 0.91,
                    "probabilities": {"ad": 0.92, "normal": 0.08},
                }
            },
        }
        mock_post.side_effect = [fail_resp, success_resp]

        res = call_clef_systemone("加入飆股群組獲利翻倍")
        self.assertTrue(res["success"])
        self.assertTrue(res["is_ad"])
        self.assertEqual(res["endpoint_used"], FALLBACK_CLEF_URL)
        self.assertEqual(mock_post.call_count, 2)

    @patch("requests.post", side_effect=Exception("Connection refused"))
    def test_call_clef_systemone_both_fail_graceful_degradation(self, mock_post):
        # Both endpoints fail; system must continue working without exception
        res = call_clef_systemone("Normal informative text")
        self.assertFalse(res["success"])
        self.assertFalse(res["is_ad"])
        self.assertEqual(res["choice"], "normal")
        self.assertTrue(res["fallback_triggered"])

    @patch("app.services.decision.call_clef_systemone")
    def test_is_advertisement_content_caching(self, mock_clef):
        mock_clef.return_value = {
            "success": True,
            "is_ad": True,
            "choice": "ad",
            "confidence": 0.98,
            "probabilities": {"ad": 0.98, "normal": 0.02},
            "prob_ad": 0.98,
        }

        text = "這是一篇極具商業推銷性質的廣告文案，點擊購買優惠券立即折抵一千元！"
        is_ad_1, meta_1 = is_advertisement_content(text)
        self.assertTrue(is_ad_1)
        self.assertFalse(meta_1.get("cached", False))
        self.assertEqual(mock_clef.call_count, 1)

        # Second call with the same text must HIT the in-memory cache
        is_ad_2, meta_2 = is_advertisement_content(text)
        self.assertTrue(is_ad_2)
        self.assertTrue(meta_2.get("cached", False))
        # mock_clef should NOT be called again
        self.assertEqual(mock_clef.call_count, 1)

    @patch("app.services.decision.call_clef_systemone")
    def test_is_advertisement_content_url_cache(self, mock_clef):
        mock_clef.return_value = {
            "success": True,
            "is_ad": False,
            "choice": "normal",
            "confidence": 0.95,
            "probabilities": {"ad": 0.05, "normal": 0.95},
            "prob_ad": 0.05,
        }

        url = "https://example.com/clean-article"
        content = "這是一篇乾淨的科技技術分析教學文章。"
        is_ad_1, meta_1 = is_advertisement_content(content, url=url)
        self.assertFalse(is_ad_1)
        self.assertEqual(mock_clef.call_count, 1)

        # Query again with just the URL
        is_ad_2, meta_2 = is_advertisement_content("", url=url)
        self.assertFalse(is_ad_2)
        self.assertTrue(meta_2.get("cached", False))
        self.assertEqual(mock_clef.call_count, 1)

    def test_is_advertisement_content_short_text_skipped(self):
        is_ad, meta = is_advertisement_content("你好")
        self.assertFalse(is_ad)
        self.assertEqual(meta.get("reason"), "too_short")

    def test_mongo_persistent_cache_lookup(self):
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "_id": "hash:fakehash123",
            "decision": {
                "is_ad": True,
                "choice": "ad",
                "prob_ad": 0.95,
            },
        }

        cached = get_cached_decision(["hash:fakehash123"], mongo_collection=mock_collection)
        self.assertIsNotNone(cached)
        self.assertTrue(cached.get("is_ad"))
        mock_collection.find_one.assert_called_once_with({"_id": "hash:fakehash123"})

    def test_fastapi_summarize_ad_detection(self):
        from fastapi.testclient import TestClient
        from api import app as fastapi_app, valid_tokens

        client = TestClient(fastapi_app)
        sample_token = list(valid_tokens)[0]

        with patch.dict("sys.modules", {"app.legacy": MagicMock()}):
            import sys
            mock_legacy = sys.modules["app.legacy"]
            mock_legacy.process_user_input.return_value = ["點擊加入高獲利股票群組，每天領取飆股推薦！"]
            mock_legacy.is_url.return_value = False
            mock_legacy.get_web_title.return_value = "Text Summary"

            with patch("app.services.decision.is_advertisement_content") as mock_ad_check:
                mock_ad_check.return_value = (True, {"is_ad": True, "prob_ad": 0.99, "cached": False})
                with patch("api.run_blocking") as mock_run:
                    mock_run.side_effect = lambda fn, *args, **kwargs: fn(*args, **kwargs)
                    response = client.post(
                        "/api/v1/summarize",
                        json={"input": "點擊加入高獲利股票群組，每天領取飆股推薦！"},
                        headers={"Authorization": f"Bearer {sample_token}"},
                    )
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    self.assertEqual(data["status"], "hidden")
                    self.assertTrue(data["is_ad"])
                    self.assertIn("廣告", data["summary"])


if __name__ == "__main__":
    unittest.main()
