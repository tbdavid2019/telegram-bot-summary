from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.api import app as fastapi_app, valid_tokens
from app.services import api_keys
from app.services.api_keys import (
    APIKeyManager,
    KEY_PREFIX,
    KeyAlreadyExistsError,
    KeyNotFoundError,
    build_curl_usage_guide,
    detect_public_ip,
    get_bot_scope,
    hash_api_key,
    is_candidate_dynamic_api_key,
    is_telegram_user_allowed,
    mask_api_key,
    record_observed_base_url,
    resolve_api_base_url,
)


class FakeDeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class FakeUpdateResult:
    def __init__(self, matched_count: int) -> None:
        self.matched_count = matched_count


class FakeMongoCollection:
    """In-memory MongoDB collection double enforcing _id uniqueness (and optional secondary indexes)."""

    def __init__(self, enforce_secondary_indexes: bool = False) -> None:
        self.docs: dict[str, dict] = {}
        self.indexes: list[tuple[list[tuple[str, int]], bool]] = []
        self.enforce_secondary_indexes = enforce_secondary_indexes

    def create_index(self, keys, unique: bool = False):
        self.indexes.append((list(keys), unique))

    @staticmethod
    def _matches(doc: dict, query: dict) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    def find_one(self, query: dict):
        if "_id" in query and len(query) == 1:
            doc = self.docs.get(query["_id"])
            return dict(doc) if doc is not None else None
        for doc in self.docs.values():
            if self._matches(doc, query):
                return dict(doc)
        return None

    def insert_one(self, doc: dict):
        doc_copy = dict(doc)
        doc_id = doc_copy.get("_id")
        if doc_id is not None and doc_id in self.docs:
            raise RuntimeError("E11000 duplicate key error collection: api_keys index: _id_")
        if self.enforce_secondary_indexes:
            for existing in self.docs.values():
                if (
                    existing.get("bot_scope") == doc_copy.get("bot_scope")
                    and existing.get("telegram_id") == doc_copy.get("telegram_id")
                ):
                    raise RuntimeError("E11000 duplicate key error on (bot_scope, telegram_id)")
                if existing.get("key_hash") == doc_copy.get("key_hash"):
                    raise RuntimeError("E11000 duplicate key error on key_hash")
        key = str(doc_id if doc_id is not None else len(self.docs))
        self.docs[key] = doc_copy

    def replace_one(self, query: dict, replacement: dict, upsert: bool = False):
        for key, doc in list(self.docs.items()):
            if self._matches(doc, query):
                rep = dict(replacement)
                rep.setdefault("_id", key)
                self.docs[key] = rep
                return FakeUpdateResult(1)
        if upsert:
            self.insert_one(replacement)
            return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    def update_one(self, query: dict, update: dict):
        for doc in self.docs.values():
            if self._matches(doc, query):
                for k, v in update.get("$set", {}).items():
                    doc[k] = v
                return FakeUpdateResult(1)
        return FakeUpdateResult(0)

    def delete_one(self, query: dict) -> FakeDeleteResult:
        for key, doc in list(self.docs.items()):
            if self._matches(doc, query):
                self.docs.pop(key)
                return FakeDeleteResult(1)
        return FakeDeleteResult(0)


def _reset_api_key_globals() -> None:
    with api_keys._base_url_lock:
        api_keys._observed_base_url = None
        api_keys._public_ip_cache = None
    with api_keys._manager_lock:
        api_keys._default_manager = None


class APIKeysServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        _reset_api_key_globals()

    def tearDown(self) -> None:
        _reset_api_key_globals()

    def test_get_bot_scope_isolation_and_no_raw_token_leak(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual("default", get_bot_scope())
        self.assertEqual("default", get_bot_scope("   "))

        token_a = "111111:AAA_private_bot_token"
        token_b = "222222:BBB_public_bot_token"
        scope_a = get_bot_scope(token_a)
        scope_b = get_bot_scope(token_b)

        self.assertEqual(12, len(scope_a))
        self.assertEqual(12, len(scope_b))
        self.assertNotEqual(scope_a, scope_b)
        self.assertNotIn("AAA_private", scope_a)
        self.assertNotIn("BBB_public", scope_b)

    def test_cross_env_bot_scope_isolation_on_shared_mongo_collection(self):
        shared_col = FakeMongoCollection()
        mgr_private = APIKeyManager(mongo_collection=shared_col, bot_scope=get_bot_scope("private-bot-token"))
        mgr_public = APIKeyManager(mongo_collection=shared_col, bot_scope=get_bot_scope("public-bot-token"))

        res_a = mgr_private.create_key(123456789)
        res_b = mgr_public.create_key(123456789)

        self.assertEqual(2, len(shared_col.docs))
        with patch.dict(os.environ, {"ALLOWED_USERS": ""}, clear=False):
            self.assertTrue(mgr_private.verify_key(res_a["api_key"]))
            self.assertTrue(mgr_public.verify_key(res_b["api_key"]))
            self.assertFalse(mgr_public.verify_key(res_a["api_key"]))
            self.assertFalse(mgr_private.verify_key(res_b["api_key"]))

            rotated_a = mgr_private.rotate_key(123456789)
            self.assertFalse(mgr_private.verify_key(res_a["api_key"]))
            self.assertTrue(mgr_private.verify_key(rotated_a["api_key"]))
            self.assertTrue(mgr_public.verify_key(res_b["api_key"]))

    def test_deterministic_id_enforces_single_key_and_rotate_rejects_missing_or_revoked(self):
        # Secondary indexes NOT enforced by fake collection: _id uniqueness alone must block duplicates
        col = FakeMongoCollection(enforce_secondary_indexes=False)
        mgr = APIKeyManager(mongo_collection=col, bot_scope="scope_1")

        # Rotating before any key exists raises KeyNotFoundError
        with self.assertRaises(KeyNotFoundError):
            mgr.rotate_key("998877")

        created = mgr.create_key("998877")
        raw_1 = created["api_key"]
        self.assertTrue(raw_1.startswith(KEY_PREFIX))
        self.assertIn("scope_1:998877", col.docs)

        with self.assertRaises(KeyAlreadyExistsError):
            mgr.create_key("998877")

        with patch.dict(os.environ, {"ALLOWED_USERS": ""}, clear=False):
            self.assertTrue(mgr.verify_key(raw_1))

            rotated = mgr.rotate_key("998877")
            raw_2 = rotated["api_key"]
            self.assertTrue(rotated["rotated"])
            self.assertNotEqual(raw_1, raw_2)
            self.assertEqual(created["created_at"], rotated["created_at"])
            self.assertFalse(mgr.verify_key(raw_1))
            self.assertTrue(mgr.verify_key(raw_2))

            # Revoke, then rotate must NOT resurrect revoked key
            self.assertTrue(mgr.revoke_key("998877"))
            self.assertFalse(mgr.verify_key(raw_2))
            with self.assertRaises(KeyNotFoundError):
                mgr.rotate_key("998877")
            self.assertIsNone(mgr.get_key_metadata("998877"))

    def test_concurrent_verify_and_rotate_revoke_across_shared_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = os.path.join(tmpdir, "shared_keys.json")
            mgr_writer = APIKeyManager(mongo_collection=None, bot_scope="conc_scope", fallback_file=key_file)
            mgr_verifier = APIKeyManager(mongo_collection=None, bot_scope="conc_scope", fallback_file=key_file)

            with patch.dict(os.environ, {"ALLOWED_USERS": ""}, clear=False):
                old_key = mgr_writer.create_key("777")["api_key"]
                self.assertTrue(mgr_verifier.verify_key(old_key))

                def verify_old_repeatedly():
                    return [mgr_verifier.verify_key(old_key) for _ in range(15)]

                with ThreadPoolExecutor(max_workers=4) as pool:
                    fut_rotate = pool.submit(mgr_writer.rotate_key, "777")
                    fut_reads = [pool.submit(verify_old_repeatedly) for _ in range(3)]
                    new_key = fut_rotate.result()["api_key"]
                    for f in fut_reads:
                        f.result()

                # Immediately after rotate completes, second independent manager sees old=False, new=True
                self.assertFalse(mgr_verifier.verify_key(old_key))
                self.assertTrue(mgr_verifier.verify_key(new_key))

                self.assertTrue(mgr_writer.revoke_key("777"))
                self.assertFalse(mgr_verifier.verify_key(new_key))

    def test_allowed_users_revocation_immediately_invalidates_dynamic_key(self):
        col = FakeMongoCollection()
        mgr = APIKeyManager(mongo_collection=col, bot_scope="allow_scope")
        key_111 = mgr.create_key("111")["api_key"]

        with patch.dict(os.environ, {"ALLOWED_USERS": "111,222"}, clear=False):
            self.assertTrue(is_telegram_user_allowed("111"))
            self.assertTrue(mgr.verify_key(key_111))

        # Remove 111 from ALLOWED_USERS -> key must immediately fail verification
        with patch.dict(os.environ, {"ALLOWED_USERS": "222"}, clear=False):
            self.assertFalse(is_telegram_user_allowed("111"))
            self.assertFalse(mgr.verify_key(key_111))

        # Empty ALLOWED_USERS (public mode) allows all valid keys
        with patch.dict(os.environ, {"ALLOWED_USERS": ""}, clear=False):
            self.assertTrue(mgr.verify_key(key_111))

    def test_plaintext_key_is_never_stored_or_returned_in_metadata(self):
        col = FakeMongoCollection()
        mgr = APIKeyManager(mongo_collection=col, bot_scope="scope_hash")

        created = mgr.create_key("user_1")
        raw_key = created["api_key"]
        expected_hash = hash_api_key(raw_key)

        stored_doc = col.docs["scope_hash:user_1"]
        self.assertEqual(expected_hash, stored_doc["key_hash"])
        self.assertNotIn(raw_key, json.dumps(stored_doc))

        meta = mgr.get_key_metadata("user_1")
        self.assertIsNotNone(meta)
        self.assertEqual(created["masked_key"], meta["masked_key"])
        self.assertNotIn("key_hash", meta)
        self.assertNotIn("api_key", meta)
        self.assertNotIn(raw_key, json.dumps(meta))

    def test_corrupted_json_fallback_raises_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            corrupted_file = os.path.join(tmpdir, "corrupted.json")
            Path(corrupted_file).write_text("{broken json!!!", encoding="utf-8")

            mgr = APIKeyManager(mongo_collection=None, bot_scope="corrupt_scope", fallback_file=corrupted_file)
            with self.assertRaises(RuntimeError):
                mgr.create_key("u1")
            with self.assertRaises(RuntimeError):
                mgr.get_key_metadata("u1")
            with self.assertRaises(RuntimeError):
                mgr.verify_key("oli_" + "a" * 32)

            # Original corrupted content must remain untouched (not wiped!)
            self.assertEqual("{broken json!!!", Path(corrupted_file).read_text(encoding="utf-8"))

    def test_fallback_file_and_in_memory_modes_without_mongodb(self):
        with patch.dict(os.environ, {"MONGO_URI": "", "ALLOWED_USERS": ""}, clear=False):
            mem_mgr = APIKeyManager(mongo_collection=None, bot_scope="mem_scope", fallback_file="")
            k1 = mem_mgr.create_key("u1")["api_key"]
            self.assertTrue(mem_mgr.verify_key(k1))
            with self.assertRaises(KeyAlreadyExistsError):
                mem_mgr.create_key("u1")
            self.assertTrue(mem_mgr.revoke_key("u1"))
            self.assertFalse(mem_mgr.verify_key(k1))

            with tempfile.TemporaryDirectory() as tmpdir:
                key_file = os.path.join(tmpdir, "nested", "keys.json")
                file_mgr_1 = APIKeyManager(mongo_collection=None, bot_scope="file_scope", fallback_file=key_file)
                k_file = file_mgr_1.create_key("u2")["api_key"]

                raw_json = Path(key_file).read_text(encoding="utf-8")
                self.assertNotIn(k_file, raw_json)
                self.assertIn(hash_api_key(k_file), raw_json)

                file_mgr_2 = APIKeyManager(mongo_collection=None, bot_scope="file_scope", fallback_file=key_file)
                self.assertTrue(file_mgr_2.verify_key(k_file))
                rotated = file_mgr_2.rotate_key("u2")
                self.assertFalse(file_mgr_2.verify_key(k_file))
                self.assertTrue(file_mgr_2.verify_key(rotated["api_key"]))

    def test_trusted_hosts_and_url_port_validation(self):
        # Empty API_TRUSTED_HOSTS disables dynamic host learning completely
        with patch.dict(os.environ, {"API_TRUSTED_HOSTS": ""}, clear=False):
            self.assertFalse(record_observed_base_url("https", "api.example.com"))

        # With API_TRUSTED_HOSTS, only whitelisted valid external hosts are accepted
        with patch.dict(os.environ, {"API_TRUSTED_HOSTS": "api.example.com"}, clear=False):
            self.assertFalse(record_observed_base_url("https", "attacker.example.com"))
            self.assertFalse(record_observed_base_url("https", "localhost"))
            self.assertFalse(record_observed_base_url("https", "127.0.0.1:8001"))
            self.assertFalse(record_observed_base_url("https", "evil.com\r\nX-Test: 1"))
            self.assertFalse(record_observed_base_url("https", "api.example.com/path"))
            self.assertTrue(record_observed_base_url("https, http", "api.example.com:8443"))

        # Invalid API_PORT values safely fall back to 8001
        for bad_port in ("", "abc", "0", "-5", "70000"):
            with patch.dict(os.environ, {"API_PUBLIC_URL": "", "API_PORT": bad_port}, clear=False):
                with patch("app.services.api_keys.detect_public_ip", return_value=None):
                    _reset_api_key_globals()
                    self.assertEqual(("http://localhost:8001", "localhost"), resolve_api_base_url())

        # Invalid API_PUBLIC_URL (userinfo, query, fragment, quotes) are rejected
        bad_env_urls = [
            "https://user:pass@example.com",
            "https://example.com?token=1",
            "https://example.com#frag",
            "https://example.com'bad",
            "ftp://example.com",
        ]
        for bad_url in bad_env_urls:
            with patch.dict(os.environ, {"API_PUBLIC_URL": bad_url, "API_PORT": "8001"}, clear=False):
                with patch("app.services.api_keys.detect_public_ip", return_value=None):
                    _reset_api_key_globals()
                    self.assertEqual(("http://localhost:8001", "localhost"), resolve_api_base_url())

        with patch.dict(os.environ, {"API_PUBLIC_URL": "https://summary.david888.com/"}, clear=False):
            self.assertEqual(("https://summary.david888.com", "env"), resolve_api_base_url())

    def test_detect_public_ip_caches_success_and_short_caches_failure(self):
        private_resp = SimpleNamespace(status_code=200, text="10.0.0.8\n")
        public_resp = SimpleNamespace(status_code=200, text="1.2.3.4\n")
        with patch("app.services.api_keys.requests.get", side_effect=[private_resp, public_resp]) as mock_get:
            ip1 = detect_public_ip(timeout=1.0)
            ip2 = detect_public_ip(timeout=1.0)
        self.assertEqual("1.2.3.4", ip1)
        self.assertEqual("1.2.3.4", ip2)
        self.assertEqual(2, mock_get.call_count)

        # Offline failure is short-cached (60s) so repeated calls don't re-hit network immediately
        _reset_api_key_globals()
        with patch("app.services.api_keys.requests.get", side_effect=RuntimeError("network down")) as mock_fail:
            self.assertIsNone(detect_public_ip(timeout=0.5))
            self.assertIsNone(detect_public_ip(timeout=0.5))
        self.assertEqual(2, mock_fail.call_count)

    def test_build_curl_usage_guide_shell_quoting_and_http_warning(self):
        http_guide = build_curl_usage_guide("http://203.0.113.5:8001", api_key="oli_test_key_123")
        self.assertIn("http://203.0.113.5:8001/health", http_guide)
        self.assertIn("http://203.0.113.5:8001/api/v1/summarize", http_guide)
        self.assertIn("Authorization: Bearer oli_test_key_123", http_guide)
        self.assertIn('"language":"zh-TW"', http_guide)
        self.assertIn("API_PUBLIC_URL", http_guide)

        # Injection characters in key/url are safely shell-quoted
        injected_guide = build_curl_usage_guide("https://example.com/'evil", api_key="oli_'$(whoami)")
        self.assertNotIn("https://example.com/'evil/health -", injected_guide)
        self.assertIn("'\"'\"'", injected_guide)

        https_guide = build_curl_usage_guide("https://summary.example.com/")
        self.assertIn("https://summary.example.com/health", https_guide)
        self.assertIn("Authorization: Bearer <YOUR_API_KEY>", https_guide)
        self.assertNotIn("目前為 HTTP 端點", https_guide)

    def test_fastapi_host_poisoning_prevention_and_auth_hardening(self):
        col = FakeMongoCollection()
        mgr = APIKeyManager(mongo_collection=col, bot_scope="fastapi_scope")
        dyn_key_1 = mgr.create_key("555666")["api_key"]
        static_token = next(iter(valid_tokens))

        client = TestClient(fastapi_app)
        with (
            patch("app.services.api_keys.get_api_key_manager", return_value=mgr),
            patch("app.api.run_blocking", side_effect=lambda fn, *args, **kwargs: fn(*args, **kwargs)),
            patch.dict("sys.modules", {"app.legacy": MagicMock()}),
            patch.dict(
                os.environ,
                {
                    "API_PUBLIC_URL": "",
                    "API_TRUSTED_HOSTS": "summary.example.com",
                    "API_TRUST_PROXY_HEADERS": "false",
                    "ALLOWED_USERS": "555666",
                },
                clear=False,
            ),
        ):
            mock_legacy = sys.modules["app.legacy"]
            mock_legacy.process_user_input.return_value = ["Mock paragraph"]
            mock_legacy.summarize.return_value = ("TITLE: Test Title\nSummary body", "Test Title")
            mock_legacy.get_web_title.return_value = "Raw Title"

            # 1. Unauthenticated 401/404 with trusted or attacker Host must NEVER poison observed URL
            res_401 = client.post(
                "/api/v1/summarize",
                json={"input": "hi"},
                headers={"Authorization": "Bearer bad", "Host": "summary.example.com", "X-Forwarded-Host": "attacker.com"},
            )
            self.assertEqual(401, res_401.status_code)
            res_404 = client.get("/not-found", headers={"Host": "summary.example.com"})
            self.assertEqual(404, res_404.status_code)
            with patch("app.services.api_keys.detect_public_ip", return_value=None):
                self.assertEqual(("http://localhost:8001", "localhost"), resolve_api_base_url())

            # 2. Non-oli_ garbage token does NOT query DB/manager
            with patch("app.api.verify_user_api_key") as mock_verify:
                res_garbage = client.post(
                    "/api/v1/summarize",
                    json={"input": "hi"},
                    headers={"Authorization": "Bearer not-an-oli-token"},
                )
                self.assertEqual(401, res_garbage.status_code)
                mock_verify.assert_not_called()

            # 3. Non-ASCII token returns 401 cleanly (no TypeError -> 500)
            res_non_ascii = client.post(
                "/api/v1/summarize",
                json={"input": "hi"},
                headers={"Authorization": "Bearer invalid_ascii_prefix"},
            )
            self.assertEqual(401, res_non_ascii.status_code)
            self.assertFalse(is_candidate_dynamic_api_key("oli_中文金鑰測試123456789012"))

            # 4. Authenticated request with proxy headers UNTRUSTED ignores X-Forwarded-Host
            res_untrusted_proxy = client.post(
                "/api/v1/summarize",
                json={"input": "Valid test content"},
                headers={
                    "Authorization": f"Bearer {static_token}",
                    "X-Forwarded-Proto": "https",
                    "X-Forwarded-Host": "summary.example.com",
                },
            )
            self.assertEqual(200, res_untrusted_proxy.status_code)
            with patch("app.services.api_keys.detect_public_ip", return_value=None):
                self.assertEqual(("http://localhost:8001", "localhost"), resolve_api_base_url())

            # 5. Authenticated request with API_TRUST_PROXY_HEADERS=true records ONLY API_TRUSTED_HOSTS
            with patch.dict(os.environ, {"API_TRUST_PROXY_HEADERS": "true"}, clear=False):
                client.post(
                    "/api/v1/summarize",
                    json={"input": "Valid test content"},
                    headers={
                        "Authorization": f"Bearer {static_token}",
                        "X-Forwarded-Proto": "https",
                        "X-Forwarded-Host": "attacker.example.com",
                    },
                )
                with patch("app.services.api_keys.detect_public_ip", return_value=None):
                    self.assertEqual(("http://localhost:8001", "localhost"), resolve_api_base_url())

                client.post(
                    "/api/v1/summarize",
                    json={"input": "Valid test content"},
                    headers={
                        "Authorization": f"Bearer {static_token}",
                        "X-Forwarded-Proto": "https",
                        "X-Forwarded-Host": "summary.example.com",
                    },
                )
                self.assertEqual(("https://summary.example.com", "observed"), resolve_api_base_url())

            # 6. Dynamic key works, ALLOWED_USERS removal immediately returns 401
            res_dyn = client.post(
                "/api/v1/summarize",
                json={"input": "Valid test content"},
                headers={"Authorization": f"Bearer {dyn_key_1}"},
            )
            self.assertEqual(200, res_dyn.status_code)

            with patch.dict(os.environ, {"ALLOWED_USERS": "999999"}, clear=False):
                res_removed = client.post(
                    "/api/v1/summarize",
                    json={"input": "Valid test content"},
                    headers={"Authorization": f"Bearer {dyn_key_1}"},
                )
                self.assertEqual(401, res_removed.status_code)

            # 7. Rotate immediately returns 401 for old key and 200 for new key
            dyn_key_2 = mgr.rotate_key("555666")["api_key"]
            self.assertEqual(
                401,
                client.post(
                    "/api/v1/summarize",
                    json={"input": "Valid test content"},
                    headers={"Authorization": f"Bearer {dyn_key_1}"},
                ).status_code,
            )
            self.assertEqual(
                200,
                client.post(
                    "/api/v1/summarize",
                    json={"input": "Valid test content"},
                    headers={"Authorization": f"Bearer {dyn_key_2}"},
                ).status_code,
            )

            # 8. Storage exception during dynamic key verification returns 503 (not 500)
            with patch("app.api.verify_user_api_key", side_effect=RuntimeError("db down")):
                res_503 = client.post(
                    "/api/v1/summarize",
                    json={"input": "Valid test content"},
                    headers={"Authorization": f"Bearer {dyn_key_2}"},
                )
                self.assertEqual(503, res_503.status_code)

    def test_verify_token_utf8_compare_digest_handles_non_ascii_token(self):
        import asyncio
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        import app.api as app_api

        fake_request = MagicMock()
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="非ASCII測試金鑰🔑")
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(app_api.verify_token(fake_request, creds))
        self.assertEqual(401, ctx.exception.status_code)


class TelegramApiKeyCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _reset_api_key_globals()

    def tearDown(self) -> None:
        _reset_api_key_globals()

    async def test_apikey_command_rejects_group_chat_and_allows_private_chat(self):
        import app.legacy as legacy

        col = FakeMongoCollection()
        mgr = APIKeyManager(mongo_collection=col, bot_scope="tg_scope")

        bot_mock = MagicMock()
        bot_mock.send_message = AsyncMock()
        bot_mock.edit_message_text = AsyncMock()
        context = SimpleNamespace(bot=bot_mock, user_data={})

        group_update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=100, type="group"),
            effective_user=SimpleNamespace(id=111),
        )
        with patch.object(legacy, "show_processing", 0), patch.object(legacy, "allowed_users", ""):
            await legacy.handle_apikey(group_update, context)
        bot_mock.send_message.assert_awaited_once()
        self.assertIn("私訊", bot_mock.send_message.call_args.kwargs["text"])

        private_update = SimpleNamespace(
            effective_chat=SimpleNamespace(id=111, type="private"),
            effective_user=SimpleNamespace(id=111),
        )
        with (
            patch.object(legacy, "show_processing", 0),
            patch.object(legacy, "allowed_users", ""),
            patch.object(legacy, "get_api_key_manager", return_value=mgr),
            patch.object(legacy, "resolve_api_base_url", return_value=("https://api.example.com", "env")),
        ):
            await legacy.handle_apikey(private_update, context)

        self.assertEqual(2, bot_mock.send_message.await_count)
        sent_kwargs = bot_mock.send_message.call_args.kwargs
        self.assertEqual("HTML", sent_kwargs["parse_mode"])
        self.assertIn("https://api.example.com", sent_kwargs["text"])

    async def test_button_click_guards_and_apikey_lifecycle_including_missing_rotate(self):
        import app.legacy as legacy

        col = FakeMongoCollection()
        mgr = APIKeyManager(mongo_collection=col, bot_scope="tg_btn_scope")

        # 1. Unauthorized user blocked by ALLOWED_USERS guard
        unauth_query = MagicMock()
        unauth_query.data = "apikey:create"
        unauth_query.answer = AsyncMock()
        unauth_query.edit_message_text = AsyncMock()
        unauth_update = SimpleNamespace(
            callback_query=unauth_query,
            effective_user=SimpleNamespace(id=999),
            effective_chat=SimpleNamespace(id=999, type="private"),
        )
        with patch.object(legacy, "allowed_users", "111,222"):
            await legacy.handle_button_click(unauth_update, SimpleNamespace(bot=MagicMock(), user_data={}))
        unauth_query.answer.assert_awaited_once_with("Sorry, you are not authorized to use this bot.", show_alert=True)
        unauth_query.edit_message_text.assert_not_awaited()

        # 2. Group chat apikey:* callback is blocked even for allowed user
        group_query = MagicMock()
        group_query.data = "apikey:create"
        group_query.answer = AsyncMock()
        group_query.edit_message_text = AsyncMock()
        group_update = SimpleNamespace(
            callback_query=group_query,
            effective_user=SimpleNamespace(id=111),
            effective_chat=SimpleNamespace(id=-100123, type="supergroup"),
        )
        with patch.object(legacy, "allowed_users", "111"):
            await legacy.handle_button_click(group_update, SimpleNamespace(bot=MagicMock(), user_data={}))
        self.assertIn("私訊", group_query.edit_message_text.call_args[0][0])

        # 3. Authorized private chat lifecycle: create -> rotate_confirm -> rotate_exec -> revoke_exec -> rotate_exec(missing) -> cancel
        def make_update(data: str):
            q = MagicMock()
            q.data = data
            q.answer = AsyncMock()
            q.edit_message_text = AsyncMock()
            upd = SimpleNamespace(
                callback_query=q,
                effective_user=SimpleNamespace(id=111),
                effective_chat=SimpleNamespace(id=111, type="private"),
            )
            return upd, q

        ctx = SimpleNamespace(bot=MagicMock(), user_data={})
        with (
            patch.object(legacy, "allowed_users", "111"),
            patch.object(legacy, "get_api_key_manager", return_value=mgr),
            patch.object(legacy, "resolve_api_base_url", return_value=("https://api.example.com", "env")),
        ):
            upd_create, q_create = make_update("apikey:create")
            await legacy.handle_button_click(upd_create, ctx)
            create_text = q_create.edit_message_text.call_args.kwargs["text"]
            self.assertIn("API Key 產生成功", create_text)
            self.assertIn(KEY_PREFIX, create_text)

            upd_rot_conf, q_rot_conf = make_update("apikey:rotate_confirm")
            await legacy.handle_button_click(upd_rot_conf, ctx)
            self.assertIn("舊金鑰將立即失效", q_rot_conf.edit_message_text.call_args.kwargs["text"])

            upd_rot_exec, q_rot_exec = make_update("apikey:rotate_exec")
            await legacy.handle_button_click(upd_rot_exec, ctx)
            self.assertIn("API Key 輪換成功", q_rot_exec.edit_message_text.call_args.kwargs["text"])

            upd_rev_exec, q_rev_exec = make_update("apikey:revoke_exec")
            await legacy.handle_button_click(upd_rev_exec, ctx)
            self.assertIn("已撤銷", q_rev_exec.edit_message_text.call_args.kwargs["text"])
            self.assertIsNone(mgr.get_key_metadata(111))

            # Stale rotate button click after revoke handles KeyNotFoundError gracefully
            upd_rot_missing, q_rot_missing = make_update("apikey:rotate_exec")
            await legacy.handle_button_click(upd_rot_missing, ctx)
            self.assertIn("目前沒有可輪換的 API Key", q_rot_missing.edit_message_text.call_args.kwargs["text"])

            upd_cancel, q_cancel = make_update("apikey:cancel")
            await legacy.handle_button_click(upd_cancel, ctx)
            self.assertIn("已取消操作", q_cancel.edit_message_text.call_args.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
