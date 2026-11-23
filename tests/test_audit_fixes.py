import os
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


class AuditFixesTests(unittest.IsolatedAsyncioTestCase):
    async def test_show_processing_zero_does_not_crash_commands(self):
        import app.legacy as legacy

        for action, text in (
            ("start", "/start"),
            ("help", "/help"),
            ("language", "/lang"),
            ("clear_context", "/clear"),
            ("show_context", "/context"),
            ("adfilter", "/adfilter"),
            ("model", "/model"),
            ("boa", "/boa"),
            ("tarot", "/tarot"),
            ("yiyu", "/yiyu"),
        ):
            bot_mock = MagicMock()
            bot_mock.send_message = AsyncMock()
            bot_mock.edit_message_text = AsyncMock()
            ctx = SimpleNamespace(bot=bot_mock, user_data={})
            upd = SimpleNamespace(
                effective_chat=SimpleNamespace(id=123, type="private"),
                effective_user=SimpleNamespace(id=123),
                message=SimpleNamespace(text=text),
            )
            with (
                patch.object(legacy, "show_processing", 0),
                patch.object(legacy, "allowed_users", ""),
                patch.object(legacy, "_fetch_boa_answer", return_value="Yes"),
            ):
                await legacy.handle(action, upd, ctx)
            bot_mock.send_message.assert_awaited()
            bot_mock.edit_message_text.assert_not_awaited()

    async def test_yt2audio_and_yt2text_enforce_auth_ssrf_and_error_matching(self):
        import app.legacy as legacy

        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        bot_mock.send_document = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={})

        # 1. Unauthorized user blocked
        unauth_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=999),
            effective_user=SimpleNamespace(id=999),
            message=SimpleNamespace(text="/yt2text https://youtube.com/watch?v=123"),
        )
        with patch.dict(os.environ, {"ALLOWED_USERS": "111"}, clear=False):
            await legacy.handle_yt2text(unauth_upd, ctx)
            await legacy.handle_yt2audio(unauth_upd, ctx)
        self.assertEqual(bot_mock.send_message.await_count, 2)
        self.assertIn("not authorized", bot_mock.send_message.call_args.kwargs["text"])

        # 2. SSRF URL blocked
        bot_mock.send_message.reset_mock()
        ssrf_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(text="/yt2audio http://127.0.0.1:8001/health"),
        )
        with patch.dict(os.environ, {"ALLOWED_USERS": "111"}, clear=False):
            await legacy.handle_yt2audio(ssrf_upd, ctx)
        self.assertIn("不支援或受保護", bot_mock.send_message.call_args.kwargs["text"])

        # 3. /yt2text returns error message instead of sending transcript.txt
        bot_mock.send_message.reset_mock()
        txt_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(text="/yt2text https://example.com/video"),
        )
        with (
            patch.dict(os.environ, {"ALLOWED_USERS": "111"}, clear=False),
            patch.object(legacy, "show_processing", 0),
            patch.object(legacy, "is_safe_url", return_value=True),
            patch.object(legacy, "retrieve_video_transcript_from_url", return_value=["該影片沒有可用的字幕，且音頻轉換功能未啟用。"]),
        ):
            await legacy.handle_yt2text(txt_upd, ctx)
        bot_mock.send_document.assert_not_awaited()
        self.assertEqual(
            bot_mock.send_message.call_args.kwargs["text"],
            "該影片沒有可用的字幕，且音頻轉換功能未啟用。",
        )

    async def test_photo_upload_is_rejected_without_reading_binary_as_text(self):
        import app.legacy as legacy

        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={})
        upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(document=None, photo=[SimpleNamespace(file_id="p1")]),
        )
        with (
            patch.object(legacy, "show_processing", 0),
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "convert_document_to_markdown") as mock_conv,
        ):
            await legacy.handle("file", upd, ctx)
        mock_conv.assert_not_called()
        self.assertIn("暫不支援純圖片", bot_mock.send_message.call_args.kwargs["text"])

    async def test_box_and_boxstats_admin_gating_and_ssrf(self):
        import app.legacy as legacy
        from app.services.box import upload_url_to_box

        # SSRF blocked in box service
        with patch("app.services.box.requests.post") as mock_post:
            res = upload_url_to_box("http://169.254.169.254/latest/meta-data/")
            self.assertFalse(res["success"])
            mock_post.assert_not_called()

        # Non-admin blocked from /box and /boxstats in public mode
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={})
        upd_box = SimpleNamespace(
            effective_chat=SimpleNamespace(id=222, type="private"),
            effective_user=SimpleNamespace(id=222),
            message=SimpleNamespace(text="/box https://example.com/a.mp4"),
        )
        upd_stats = SimpleNamespace(
            effective_chat=SimpleNamespace(id=222, type="private"),
            effective_user=SimpleNamespace(id=222),
            message=SimpleNamespace(text="/boxstats"),
        )
        with (
            patch.object(legacy, "show_processing", 0),
            patch.dict(os.environ, {"ALLOWED_USERS": "", "ADMIN_USERS": "111"}, clear=False),
        ):
            await legacy.handle("box", upd_box, ctx)
            self.assertIn("管理員", bot_mock.send_message.call_args.kwargs["text"])
            await legacy.handle("boxstats", upd_stats, ctx)
            self.assertIn("管理員", bot_mock.send_message.call_args.kwargs["text"])

    async def test_casual_chat_long_reply_and_analysis_do_not_autopublish_wiki(self):
        import app.legacy as legacy

        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={}, chat_data={})
        for prompt in ("今天適合喝什麼咖啡？", "幫我比較 A 跟 B 的市場分析"):
            upd = SimpleNamespace(
                effective_chat=SimpleNamespace(id=111, type="private"),
                effective_user=SimpleNamespace(id=111),
                message=SimpleNamespace(text=prompt),
            )
            long_reply = "回覆內容：" + ("詳細解析。" * 150)
            with (
                patch.object(legacy, "show_processing", 0),
                patch.object(legacy, "allowed_users", ""),
                patch.object(legacy, "call_gpt_api", return_value=long_reply),
                patch.object(legacy, "publish_wiki_page") as mock_wiki,
            ):
                await legacy.handle("summarize", upd, ctx)
            mock_wiki.assert_not_called()

    def test_is_safe_url_fail_closed_cgnat_docker_and_redirect(self):
        from app.services.content import is_safe_url, safe_http_get

        self.assertFalse(is_safe_url("http://100.64.0.1/internal"))
        self.assertFalse(is_safe_url("http://host.docker.internal:8001/health"))
        with patch("app.services.content.socket.getaddrinfo", side_effect=socket.gaierror("DNS fail")):
            self.assertFalse(is_safe_url("https://unresolvable.internal.example/"))

        redirect_resp = MagicMock()
        redirect_resp.status_code = 302
        redirect_resp.headers = {"Location": "http://127.0.0.1:8001/secret"}
        with (
            patch("app.services.content.is_safe_url", side_effect=[True, False]),
            patch("requests.get", return_value=redirect_resp),
        ):
            with self.assertRaises(ValueError):
                safe_http_get("https://public.example.com/redir")

        # Verify TCP connection guard blocks DNS rebinding even when initial is_safe_url passed
        from app.services.content import _ssrf_checked_create_connection
        import socket as sock_mod

        rebound_addr = [(sock_mod.AF_INET, sock_mod.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
        with patch("app.services.content.socket.getaddrinfo", return_value=rebound_addr):
            with self.assertRaises(ValueError):
                _ssrf_checked_create_connection(("rebound.example.com", 80))

    def test_wiki_path_traversal_blocked(self):
        from app.services.wiki import publish_wiki_page, read_wiki_page

        res_pub = publish_wiki_page("body", path="../etc/passwd")
        self.assertFalse(res_pub["success"])
        res_read = read_wiki_page("notes?admin=true")
        self.assertFalse(res_read["success"])

    def test_api_readyz_and_rate_limit(self):
        from app.api import app as fastapi_app, valid_tokens, _RATE_LIMIT_BUCKETS, set_bot_ready
        import app.api as api_mod

        client = TestClient(fastapi_app)
        prev_ready = api_mod._BOT_READY
        _RATE_LIMIT_BUCKETS.clear()
        try:
            with patch.dict(os.environ, {"MONGO_URI": ""}, clear=False):
                set_bot_ready(False)
                unready = client.get("/readyz")
                self.assertEqual(unready.status_code, 503)

                set_bot_ready(True)
                ready = client.get("/readyz")
                self.assertEqual(ready.status_code, 200)
                self.assertEqual(ready.json()["status"], "ready")
                self.assertTrue(ready.json()["bot_ready"])

            token = next(iter(valid_tokens))
            with (
                patch.dict(os.environ, {"API_RATE_LIMIT_PER_MINUTE": "1"}, clear=False),
                patch("app.services.decision.is_decision_ad_filter_enabled", return_value=False),
                patch("app.api.run_blocking", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
                patch.dict("sys.modules", {"app.legacy": MagicMock()}),
            ):
                import sys

                mock_legacy = sys.modules["app.legacy"]
                mock_legacy.process_user_input.return_value = ["Paragraph"]
                mock_legacy.summarize.return_value = ("Summary", "Title")
                r1 = client.post("/api/v1/summarize", json={"input": "Hello world"}, headers={"Authorization": f"Bearer {token}"})
                r2 = client.post("/api/v1/summarize", json={"input": "Hello world"}, headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(r1.status_code, 200)
                self.assertEqual(r2.status_code, 429)
        finally:
            set_bot_ready(prev_ready)
            _RATE_LIMIT_BUCKETS.clear()

    def test_wiki_rejects_non_json_200_and_never_fabricates_share_url(self):
        from app.services.wiki import publish_wiki_page

        html_200 = MagicMock()
        html_200.status_code = 200
        html_200.json.side_effect = ValueError("not json")
        html_200.text = "<html>Login share page</html>"
        with patch("app.services.wiki.requests.post", return_value=html_200):
            res = publish_wiki_page("# Title\n\nBody")
        self.assertFalse(res["success"])

    def test_summarize_preserves_hashtags_and_rejects_title_only(self):
        from app.services.summarization import summarize

        out = summarize(["正文內容"], gpt_caller=lambda *a, **kw: "TITLE: 好標題\n\n#AI #LLM")
        self.assertIn("#AI #LLM", out)
        self.assertNotIn("\\#AI", out)

        title_only = summarize(["正文內容"], gpt_caller=lambda *a, **kw: "TITLE: 只有標題")
        self.assertTrue(title_only.startswith("⚠️ 摘要生成失敗"))

    def test_decision_rejects_incomplete_schema_and_prioritizes_content_hash(self):
        from app.services.decision import call_clef_systemone, is_advertisement_content, clear_decision_cache, store_cached_decision

        clear_decision_cache()
        incomplete_resp = MagicMock()
        incomplete_resp.status_code = 200
        incomplete_resp.json.return_value = {"status": "ok"}
        with patch("requests.post", return_value=incomplete_resp):
            res = call_clef_systemone("Some text to classify")
        self.assertFalse(res["success"])

        # Updated page content hash should win over stale URL cache entry
        url = "https://example.com/updated-feed"
        store_cached_decision([f"url:{url}"], {"is_ad": True, "choice": "ad", "prob_ad": 0.99})
        with patch("app.services.decision.call_clef_systemone", return_value={"success": True, "is_ad": False, "choice": "normal", "prob_ad": 0.01}) as mock_clef:
            is_ad, _ = is_advertisement_content("A" * 50 + " clean new article", url=url)
        self.assertFalse(is_ad)
        mock_clef.assert_called_once()
        clear_decision_cache()

    def test_podcast_explicit_uuid_miss_returns_none(self):
        from app.services.podcast import extract_pocketcasts_episode, is_soundon_url

        extract_pocketcasts_episode.cache_clear()
        self.assertFalse(is_soundon_url("https://example.com/?ref=soundon.fm"))
        self.assertTrue(is_soundon_url("https://player.soundon.fm/p/abc"))

        podcast_uuid = "2d1c2ae0-1136-0137-f265-1d245fc5f9cf"
        missing_ep = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "podcast": {
                "title": "Show",
                "episodes": [{"uuid": "11111111-2222-3333-4444-555555555555", "title": "Other", "url": "https://cdn.test/other.mp3"}],
            }
        }
        with patch("requests.get", return_value=resp):
            ep = extract_pocketcasts_episode(f"https://pocketcasts.com/podcast/show/{podcast_uuid}/ep/{missing_ep}")
        self.assertIsNone(ep)

    def test_summary_repository_tags_bot_scope(self):
        from app.repositories.summaries import SummaryRepository

        mock_col = MagicMock()
        repo = SummaryRepository(collection=mock_col)
        with patch.dict(os.environ, {"TELEGRAM_TOKEN": "123456:TESTTOKEN"}, clear=False):
            repo.save({"title": "Test", "bot_scope": "spoofed"})
        inserted = mock_col.insert_one.call_args[0][0]
        self.assertIn("bot_scope", inserted)
        self.assertNotEqual(inserted["bot_scope"], "spoofed")
        self.assertEqual(len(inserted["bot_scope"]), 12)

    def test_single_pass_title_cache_hits_get_web_title(self):
        import app.legacy as legacy

        url = "https://example.com/cached-article"
        legacy._cache_url_title(url, "Cached Title")
        with patch("app.legacy.is_safe_url", return_value=True), patch("app.legacy.safe_http_get") as mock_get:
            title = legacy.get_web_title(url, localize=False)
        self.assertEqual(title, "Cached Title")
        mock_get.assert_not_called()

    async def test_youtube_channel_rejected_with_reason_and_queue_continues(self):
        import asyncio
        import app.legacy as legacy

        channel_url = "https://www.youtube.com/channel/UCCTEGdb7XMWn123456"
        with (
            patch.object(legacy, "is_safe_url", return_value=True),
            patch("app.legacy.yt_dlp.YoutubeDL") as mock_ydl,
            patch.object(legacy, "scrape_text_from_url") as mock_scrape,
        ):
            res = legacy.process_user_input(channel_url)
            self.assertIsInstance(res, tuple)
            self.assertEqual(res[0], [])
            self.assertIn("UNSUPPORTED_YOUTUBE_CHANNEL", res[1])
            self.assertIn("原因：", res[1])
            self.assertFalse(legacy.is_supported_by_ytdlp(channel_url))
            mock_ydl.assert_not_called()
            mock_scrape.assert_not_called()

        # Verify timeout on one stalled URL returns explicit diagnostic reason and doesn't block subsequent URLs
        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        bot_mock.edit_message_text = AsyncMock()
        bot_mock.delete_message = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={}, chat_data={})

        stalled_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(text="https://example.com/slow-url"),
        )
        good_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(text="https://www.youtube.com/watch?v=dWNrafD9g38"),
        )

        async def _fake_run_blocking(fn, *args, **kwargs):
            if fn is legacy.process_user_input and args and args[0] == "https://example.com/slow-url":
                await asyncio.sleep(0.2)
                return ["late"]
            if fn is legacy.process_user_input:
                return ["正常的影片字幕內容"]
            if fn is legacy.get_web_title:
                return "地球上的水究竟是哪來的？"
            return fn(*args, **kwargs)

        with (
            patch.object(legacy, "show_processing", 0),
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "URL_PROCESSING_TIMEOUT_SECONDS", 0.05),
            patch.object(legacy, "run_blocking", side_effect=_fake_run_blocking),
            patch.object(legacy, "is_decision_ad_filter_enabled", return_value=False),
            patch.object(legacy, "_finalize_and_deliver_summary", new=AsyncMock()) as mock_deliver,
        ):
            await legacy.handle("summarize", stalled_upd, ctx)
            timeout_msg = bot_mock.send_message.call_args.kwargs["text"]
            self.assertIn("URL_PROCESSING_TIMEOUT", timeout_msg)

            await legacy.handle("summarize", good_upd, ctx)
            mock_deliver.assert_awaited_once()

    def test_bot_application_enables_concurrent_updates(self):
        import app.legacy as legacy

        app = legacy._build_bot_application("")
        self.assertGreater(app.concurrent_updates, 1)

    async def test_multi_url_intent_confirmation_individual_with_shared_note_and_partial_recovery(self):
        import app.legacy as legacy

        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        bot_mock.edit_message_text = AsyncMock()
        bot_mock.delete_message = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={}, chat_data={})

        multi_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(
                text=(
                    "https://www.youtube.com/watch?v=dWNrafD9g38\n"
                    "https://www.youtube.com/channel/UCCTEGdb7XMWn123456\n"
                    "https://www.youtube.com/watch?v=5ahr3tfpikc\n"
                    "請幫我整理這幾支的核心重點"
                )
            ),
        )
        with (
            patch.object(legacy, "show_processing", 0),
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "is_safe_url", return_value=True),
        ):
            await legacy.handle("summarize", multi_upd, ctx)

        # Should ask intent with buttons and pre-flight skip the channel URL
        sent_kwargs = bot_mock.send_message.call_args.kwargs
        self.assertIn("偵測到多個連結", sent_kwargs["text"])
        self.assertIn("UNSUPPORTED_YOUTUBE_CHANNEL", sent_kwargs["text"])
        self.assertIn("請幫我整理這幾支的核心重點", sent_kwargs["text"])
        batch_keys = [k for k in ctx.chat_data if k.startswith("batch_intent_")]
        self.assertEqual(len(batch_keys), 1)
        batch_id = batch_keys[0].removeprefix("batch_intent_")
        self.assertEqual(len(ctx.chat_data[batch_keys[0]]["urls"]), 2)

        # Clicking "individual" runs both valid URLs and applies shared user_note to each
        delivered_notes = []

        async def _fake_deliver(**kwargs):
            delivered_notes.append((kwargs["original_url"], kwargs["user_note"]))

        query_msg = MagicMock()
        query_msg.message_id = 500
        cb_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            callback_query=SimpleNamespace(
                data=f"batch:{batch_id}:individual",
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
                message=query_msg,
            ),
        )
        with (
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "is_decision_ad_filter_enabled", return_value=False),
            patch.object(legacy, "process_user_input", return_value=["字幕內容段落"]),
            patch.object(legacy, "get_web_title", return_value="影片標題"),
            patch.object(legacy, "_finalize_and_deliver_summary", side_effect=_fake_deliver),
        ):
            await legacy.handle_button_click(cb_upd, ctx)

        self.assertEqual(
            delivered_notes,
            [
                ("https://www.youtube.com/watch?v=dWNrafD9g38", "請幫我整理這幾支的核心重點"),
                ("https://www.youtube.com/watch?v=5ahr3tfpikc", "請幫我整理這幾支的核心重點"),
            ],
        )

    async def test_single_url_no_subtitles_offers_force_audio_recovery(self):
        import app.legacy as legacy

        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        bot_mock.edit_message_text = AsyncMock()
        bot_mock.delete_message = AsyncMock()
        ctx = SimpleNamespace(bot=bot_mock, user_data={}, chat_data={})

        upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            message=SimpleNamespace(text="https://www.youtube.com/watch?v=dWNrafD9g38"),
        )
        with (
            patch.object(legacy, "show_processing", 0),
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "process_user_input", return_value=["該影片沒有可用的字幕，且音頻轉換功能未啟用。"]),
        ):
            await legacy.handle("summarize", upd, ctx)

        err_kwargs = bot_mock.send_message.call_args.kwargs
        self.assertIn("NO_SUBTITLES", err_kwargs["text"])
        self.assertIn("請問您希望如何處理", err_kwargs["text"])
        retry_keys = [k for k in ctx.chat_data if k.startswith("url_retry_")]
        self.assertEqual(len(retry_keys), 1)
        retry_id = retry_keys[0].removeprefix("url_retry_")

        # Clicking force_audio invokes audio_transcription and delivers summary
        cb_upd = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
            callback_query=SimpleNamespace(
                data=f"url_act:{retry_id}:force_audio",
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
                message=MagicMock(message_id=600),
            ),
        )
        with (
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "is_decision_ad_filter_enabled", return_value=False),
            patch.object(legacy, "audio_transcription", return_value=["[00:05] 轉錄內容"]),
            patch.object(legacy, "get_web_title", return_value="地球上的水究竟是哪來的？"),
            patch.object(legacy, "_finalize_and_deliver_summary", new=AsyncMock()) as mock_deliver,
        ):
            await legacy.handle_button_click(cb_upd, ctx)

        mock_deliver.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
