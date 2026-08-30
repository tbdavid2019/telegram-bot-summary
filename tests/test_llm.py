"""Unit tests for the multi-tier & multi-key Fallback LLM Service."""

import os
import unittest
from unittest.mock import patch, MagicMock
import requests

from app.services.llm import (
    LLMEndpoint,
    get_configured_endpoints,
    get_available_models,
    call_llm_with_fallback,
    _normalize_model_for_endpoint,
)


class TestLLMService(unittest.TestCase):

    def test_get_configured_endpoints_discovery(self):
        env = {
            "LLM_API_KEY": "test-key-1",
            "LLM_MODEL": "gpt-4o-mini",
            "LLM_BASE_URL": "https://api.openai.com/v1",
            "LLM2_API_KEY": "test-key-2",
            "LLM2_MODEL": "llama-3.3-70b-versatile",
            "LLM2_BASE_URL": "https://api.groq.com/openai/v1",
            "LLM3_API_KEY": "test-key-3",
            "LLM3_MODEL": "gemini-1.5-flash",
            "LLM3_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
        }
        with patch.dict(os.environ, env, clear=True):
            endpoints = get_configured_endpoints()
            self.assertEqual(len(endpoints), 3)
            self.assertEqual(endpoints[0].name, "LLM1 (Primary)")
            self.assertEqual(endpoints[0].model, "gpt-4o-mini")
            self.assertEqual(endpoints[1].name, "LLM2")
            self.assertEqual(endpoints[1].model, "llama-3.3-70b-versatile")
            self.assertEqual(endpoints[2].name, "LLM3")
            self.assertEqual(endpoints[2].model, "gemini-1.5-flash")

    def test_multi_key_pool_discovery(self):
        env = {
            "LLM_API_KEY": "key1,key2,key3",
            "LLM_MODEL": "gemini-2.5-flash",
            "LLM_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
            "LLM2_API_KEY": "gsk_1,gsk_2",
            "LLM2_MODEL": "openai/gpt-oss-120b",
            "LLM2_BASE_URL": "https://api.groq.com/openai/v1",
        }
        with patch.dict(os.environ, env, clear=True):
            endpoints = get_configured_endpoints()
            self.assertEqual(len(endpoints), 5)
            self.assertEqual(endpoints[0].name, "LLM1 (Primary Key #1)")
            self.assertEqual(endpoints[1].name, "LLM1 (Primary Key #2)")
            self.assertEqual(endpoints[2].name, "LLM1 (Primary Key #3)")
            self.assertEqual(endpoints[3].name, "LLM2 (Key #1)")
            self.assertEqual(endpoints[4].name, "LLM2 (Key #2)")

    def test_groq_auto_fallback_added_when_groq_key_present(self):
        env = {
            "LLM_API_KEY": "test-key-1",
            "LLM_MODEL": "gpt-4o-mini",
            "LLM_BASE_URL": "https://api.openai.com/v1",
            "GROQ_API_KEY": "gsk_test_groq_key_1, gsk_test_groq_key_2",
        }
        with patch.dict(os.environ, env, clear=True):
            endpoints = get_configured_endpoints()
            self.assertEqual(len(endpoints), 3)
            self.assertEqual(endpoints[0].model, "gpt-4o-mini")
            self.assertTrue("Groq Auto-Fallback" in endpoints[1].name)
            self.assertTrue("Groq Auto-Fallback" in endpoints[2].name)

    def test_json_fallback_configs(self):
        import json
        configs = [
            {"name": "Backup DeepSeek", "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1", "api_key": "dsk_1"},
            {"name": "Backup OpenRouter", "model": "meta-llama/llama-3.3-70b-instruct", "base_url": "https://openrouter.ai/api/v1", "api_key": "sk-or-1"}
        ]
        env = {
            "LLM_API_KEY": "main_key",
            "LLM_MODEL": "gpt-4o-mini",
            "LLM_FALLBACK_CONFIGS": json.dumps(configs)
        }
        with patch.dict(os.environ, env, clear=True):
            endpoints = get_configured_endpoints()
            self.assertEqual(len(endpoints), 3)
            self.assertEqual(endpoints[1].name, "Backup DeepSeek")
            self.assertEqual(endpoints[1].model, "deepseek-chat")
            self.assertEqual(endpoints[2].name, "Backup OpenRouter")

    def test_get_available_models(self):
        endpoints = [
            LLMEndpoint(name="LLM1", model="gemini-1.5-flash", base_url="https://api.openai.com/v1", api_key="k1"),
            LLMEndpoint(name="LLM2", model="llama-3.3-70b-versatile", base_url="https://api.groq.com/openai/v1", api_key="k2"),
            LLMEndpoint(name="LLM3", model="gemini-1.5-flash", base_url="https://other.com/v1", api_key="k3"),  # duplicate model
        ]
        models = get_available_models(endpoints)
        self.assertEqual(models, ["gemini-1.5-flash", "llama-3.3-70b-versatile"])

    def test_normalize_model_for_endpoint(self):
        base_gemini = "https://generativelanguage.googleapis.com/v1beta/openai"
        self.assertEqual(_normalize_model_for_endpoint("models/gemini-1.5-flash", base_gemini), "gemini-1.5-flash")
        self.assertEqual(_normalize_model_for_endpoint("models/gemini-flash-latest", base_gemini), "gemini-1.5-flash")
        self.assertEqual(_normalize_model_for_endpoint("gemini-2.0-flash", base_gemini), "gemini-2.0-flash")

        base_openai = "https://api.openai.com/v1"
        self.assertEqual(_normalize_model_for_endpoint("gpt-4o-mini", base_openai), "gpt-4o-mini")

    @patch("app.services.llm.requests.post")
    def test_call_llm_primary_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello summary from primary!"}}]
        }
        mock_post.return_value = mock_resp

        endpoints = [
            LLMEndpoint(name="Primary", model="gpt-4o-mini", base_url="https://api.openai.com/v1", api_key="k1"),
            LLMEndpoint(name="Secondary", model="llama-3.3", base_url="https://api.groq.com/openai/v1", api_key="k2"),
        ]
        result = call_llm_with_fallback("Test prompt", endpoints=endpoints)
        self.assertEqual(result, "Hello summary from primary!")
        self.assertEqual(mock_post.call_count, 1)

    @patch("app.services.llm.requests.post")
    def test_call_llm_fallback_on_http_error(self, mock_post):
        resp_400 = MagicMock()
        resp_400.status_code = 400
        resp_400.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Bad Request", response=resp_400)

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "choices": [{"message": {"content": "Hello summary from fallback secondary!"}}]
        }

        mock_post.side_effect = [resp_400.raise_for_status.side_effect, resp_200]

        endpoints = [
            LLMEndpoint(name="Primary (Broken)", model="bad-model", base_url="https://broken.api/v1", api_key="k1"),
            LLMEndpoint(name="Secondary (Working)", model="llama-3.3", base_url="https://api.groq.com/openai/v1", api_key="k2"),
        ]

        result = call_llm_with_fallback("Test prompt", endpoints=endpoints)
        self.assertEqual(result, "Hello summary from fallback secondary!")
        self.assertEqual(mock_post.call_count, 2)

    @patch("app.services.llm.requests.post")
    def test_call_llm_multi_tier_fallback(self, mock_post):
        timeout_err = requests.exceptions.Timeout("Connection timed out")
        resp_500 = MagicMock()
        resp_500.status_code = 500
        resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error", response=resp_500)

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "choices": [{"message": {"content": "Success from 3rd tier!"}}]
        }

        mock_post.side_effect = [timeout_err, resp_500.raise_for_status.side_effect, resp_200]

        endpoints = [
            LLMEndpoint(name="LLM1", model="m1", base_url="https://url1/v1", api_key="k1"),
            LLMEndpoint(name="LLM2", model="m2", base_url="https://url2/v1", api_key="k2"),
            LLMEndpoint(name="LLM3", model="m3", base_url="https://url3/v1", api_key="k3"),
        ]

        result = call_llm_with_fallback("Test multi tier", endpoints=endpoints)
        self.assertEqual(result, "Success from 3rd tier!")
        self.assertEqual(mock_post.call_count, 3)

    @patch("app.services.llm.requests.post")
    def test_call_llm_selected_model_prioritization(self, mock_post):
        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = {
            "choices": [{"message": {"content": "Response from selected model"}}]
        }
        mock_post.return_value = resp_200

        endpoints = [
            LLMEndpoint(name="LLM1", model="m1", base_url="https://url1/v1", api_key="k1"),
            LLMEndpoint(name="LLM2", model="target-model", base_url="https://url2/v1", api_key="k2"),
        ]

        result = call_llm_with_fallback("Test prompt", selected_model="target-model", endpoints=endpoints)
        self.assertEqual(result, "Response from selected model")
        
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["json"]["model"], "target-model")
        self.assertTrue("url2" in mock_post.call_args[0][0])

    @patch("app.services.llm.requests.post")
    def test_call_llm_all_failed(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Failed to connect")

        endpoints = [
            LLMEndpoint(name="LLM1", model="m1", base_url="https://url1/v1", api_key="k1"),
            LLMEndpoint(name="LLM2", model="m2", base_url="https://url2/v1", api_key="k2"),
        ]

        result = call_llm_with_fallback("Test all fail", endpoints=endpoints)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
