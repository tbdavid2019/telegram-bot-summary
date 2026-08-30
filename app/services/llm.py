"""Multi-tier & Multi-Key Fallback LLM Service.

Comprehensive high-availability architecture:
1. Multi-Key Pooling: Supports comma-separated keys (e.g. key1,key2,key3) per tier with automatic key rotation on rate limits / quota errors.
2. Multi-Tier Endpoints: Scans LLM1 (Primary) through LLM20 (Secondary, Tertiary, etc.).
3. Multi-Provider Fallbacks: Auto-detects and supports Google Gemini, Groq, OpenAI, DeepSeek, OpenRouter, and custom OpenAI-compatible gateways.
4. Intelligent Intra-Provider Aliases: Recovers from 400/404 model name mismatches by trying safe aliases before failing over.
5. JSON Fallback Configs: Supports LLM_FALLBACK_CONFIGS for declaring arbitrary fallback pools.
"""

from dataclasses import dataclass
import json
import logging
import os
import re
from typing import List, Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

# Default Constants
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))


@dataclass
class LLMEndpoint:
    """Represents a configured LLM provider endpoint candidate."""
    name: str
    model: str
    base_url: str
    api_key: str
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    is_enabled: bool = True

    @property
    def clean_base_url(self) -> str:
        """Strip trailing slashes from the base URL."""
        return self.base_url.rstrip("/")


def _split_keys(key_string: Optional[str]) -> List[str]:
    """Split comma- or newline-separated API keys into a clean list."""
    if not key_string:
        return []
    keys = []
    for k in re.split(r'[\r\n,]+', key_string):
        cleaned = k.strip()
        if cleaned and cleaned not in ("YOUR_API_KEY", "YOUR_GROQ_API_KEY", "your_llm_api_key", "your_openai_api_key"):
            keys.append(cleaned)
    return keys


def get_configured_endpoints() -> List[LLMEndpoint]:
    """
    Discover all configured LLM endpoints and key pools from environment variables in priority order:
    1. Primary Tier (LLM_API_KEY / LLM1_API_KEY / OPENAI_API_KEY) - handles multi-key lists.
    2. Multi-Tier Fallbacks (LLM2..LLM20) - handles multi-key lists per tier.
    3. JSON Structured Fallback Pool (LLM_FALLBACK_CONFIGS).
    4. Model-level Fallbacks on Primary (LLM_FALLBACK_MODELS).
    5. Auto Groq Fallbacks (GROQ_API_KEY / GROQ_FALLBACK_KEYS) if not already explicitly registered.
    """
    timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    endpoints: List[LLMEndpoint] = []

    # 1. Primary LLM (Tier 1)
    primary_raw_keys = os.environ.get("LLM_API_KEY") or os.environ.get("LLM1_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    primary_keys = _split_keys(primary_raw_keys)
    primary_model = (os.environ.get("LLM_MODEL") or os.environ.get("LLM1_MODEL") or "gpt-4o-mini").strip()
    primary_base_url = (os.environ.get("LLM_BASE_URL") or os.environ.get("LLM1_BASE_URL") or "https://api.openai.com/v1").strip()

    for idx, key in enumerate(primary_keys):
        tag = f"LLM1 (Primary Key #{idx+1})" if len(primary_keys) > 1 else "LLM1 (Primary)"
        endpoints.append(LLMEndpoint(
            name=tag,
            model=primary_model,
            base_url=primary_base_url,
            api_key=key,
            timeout=timeout,
        ))

    # 2. Multi-Tier Fallbacks (LLM2..LLM20)
    for tier in range(2, 21):
        tier_keys = _split_keys(os.environ.get(f"LLM{tier}_API_KEY", ""))
        tier_model = os.environ.get(f"LLM{tier}_MODEL", "").strip()
        tier_url = os.environ.get(f"LLM{tier}_BASE_URL", "").strip()

        if not tier_keys or not tier_model:
            continue

        if not tier_url:
            if tier_model.startswith("llama") or tier_model.startswith("gemma") or tier_model.startswith("openai/gpt-oss") or any("gsk_" in k for k in tier_keys):
                tier_url = "https://api.groq.com/openai/v1"
            else:
                tier_url = "https://api.openai.com/v1"

        for k_idx, key in enumerate(tier_keys):
            tag = f"LLM{tier} (Key #{k_idx+1})" if len(tier_keys) > 1 else f"LLM{tier}"
            endpoints.append(LLMEndpoint(
                name=tag,
                model=tier_model,
                base_url=tier_url,
                api_key=key,
                timeout=timeout,
            ))

    # 3. JSON Structured Fallback Pool (LLM_FALLBACK_CONFIGS)
    json_configs = os.environ.get("LLM_FALLBACK_CONFIGS", "").strip()
    if json_configs:
        try:
            parsed = json.loads(json_configs)
            if isinstance(parsed, list):
                for idx, item in enumerate(parsed):
                    if isinstance(item, dict) and item.get("api_key") and item.get("model"):
                        name = item.get("name", f"Custom Fallback #{idx+1}")
                        model = item.get("model")
                        url = item.get("base_url", "https://api.openai.com/v1")
                        for k in _split_keys(item.get("api_key")):
                            endpoints.append(LLMEndpoint(
                                name=name,
                                model=model,
                                base_url=url,
                                api_key=k,
                                timeout=timeout,
                            ))
        except Exception as e:
            logger.warning(f"Failed to parse LLM_FALLBACK_CONFIGS: {e}")

    # 4. Model-level Fallbacks on Primary endpoint if LLM_FALLBACK_MODELS is set
    fallback_models_env = os.environ.get("LLM_FALLBACK_MODELS", "").strip()
    if fallback_models_env and primary_keys:
        for fb_model in [m.strip() for m in fallback_models_env.split(",") if m.strip()]:
            if not any(ep.model == fb_model and ep.clean_base_url == primary_base_url.rstrip("/") for ep in endpoints):
                endpoints.append(LLMEndpoint(
                    name=f"Primary Fallback Model ({fb_model})",
                    model=fb_model,
                    base_url=primary_base_url,
                    api_key=primary_keys[0],
                    timeout=timeout,
                ))

    # 5. Auto Groq fallback if GROQ_API_KEY is present and not explicitly configured in previous tiers
    groq_keys = _split_keys(os.environ.get("GROQ_API_KEY", "") or os.environ.get("GROQ_FALLBACK_KEYS", ""))
    if groq_keys:
        groq_model = os.environ.get("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile").strip()
        # Add Groq keys if they are not already in the endpoints
        for g_idx, g_key in enumerate(groq_keys):
            if not any(ep.api_key == g_key for ep in endpoints):
                tag = f"Groq Auto-Fallback (Key #{g_idx+1})" if len(groq_keys) > 1 else f"Groq Auto-Fallback ({groq_model})"
                endpoints.append(LLMEndpoint(
                    name=tag,
                    model=groq_model,
                    base_url="https://api.groq.com/openai/v1",
                    api_key=g_key,
                    timeout=timeout,
                ))

    return endpoints


def get_available_models(endpoints: Optional[List[LLMEndpoint]] = None) -> List[str]:
    """
    Return distinct available models in order of priority.
    """
    if endpoints is None:
        endpoints = get_configured_endpoints()
    
    models: List[str] = []
    for ep in endpoints:
        if ep.model and ep.model not in models:
            models.append(ep.model)
            
    # Always guarantee at least one model name
    if not models:
        primary_model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        models.append(primary_model)
        
    return models


def _normalize_model_for_endpoint(model: str, base_url: str) -> str:
    """Normalize model string depending on provider characteristics."""
    if "generativelanguage.googleapis.com" in base_url:
        cleaned = model.removeprefix("models/")
        if cleaned in ("gemini-flash-latest", "flash-latest"):
            return "gemini-1.5-flash"
        return cleaned
    return model


def _execute_chat_completion(
    endpoint: LLMEndpoint,
    prompt: str,
    additional_messages: Optional[List[Dict[str, str]]] = None,
    timeout: Optional[float] = None
) -> str:
    """
    Send a POST request to the LLM endpoint's /chat/completions.
    Supports intelligent intra-provider model alias failover on HTTP 400/404 before throwing.
    Raises requests.exceptions.RequestException or ValueError on failure.
    """
    api_base_url = endpoint.clean_base_url
    url = f"{api_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {endpoint.api_key}",
        "Content-Type": "application/json",
    }
    
    messages = list(additional_messages or [])
    messages.append({"role": "user", "content": prompt})
    
    target_model = _normalize_model_for_endpoint(endpoint.model, endpoint.clean_base_url)
    models_to_try = [target_model]

    if "generativelanguage.googleapis.com" in api_base_url:
        for alias in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"):
            if alias not in models_to_try:
                models_to_try.append(alias)
    elif "api.groq.com" in api_base_url:
        if target_model.startswith("openai/"):
            clean_m = target_model.removeprefix("openai/")
            if clean_m not in models_to_try:
                models_to_try.append(clean_m)
        for alias in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen-2.5-32b", "deepseek-r1-distill-llama-70b"):
            if alias not in models_to_try:
                models_to_try.append(alias)
    elif "api.openai.com" in api_base_url:
        for alias in ("gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"):
            if alias not in models_to_try:
                models_to_try.append(alias)
    
    req_timeout = timeout or endpoint.timeout
    last_err = None

    for m in models_to_try:
        try:
            data = {
                "model": m,
                "messages": messages,
            }
            response = requests.post(url, headers=headers, json=data, timeout=req_timeout)
            response.raise_for_status()
            
            resp_json = response.json()
            choices = resp_json.get("choices", [])
            if not choices:
                raise ValueError("Empty choices returned from LLM provider")
                
            content = choices[0].get("message", {}).get("content", "")
            if content is None:
                raise ValueError("Null content returned in message from LLM provider")
                
            return content.strip()
        except requests.exceptions.HTTPError as http_err:
            status = getattr(getattr(http_err, 'response', None), 'status_code', None)
            if status in (400, 404) and m != models_to_try[-1]:
                last_err = http_err
                continue
            raise
        except Exception as e:
            last_err = e
            raise

    if last_err:
        raise last_err
    return ""


def call_llm_with_fallback(
    prompt: str,
    additional_messages: Optional[List[Dict[str, str]]] = None,
    use_llm2_model: bool = False,
    selected_model: Optional[str] = None,
    timeout: Optional[float] = None,
    endpoints: Optional[List[LLMEndpoint]] = None
) -> str:
    """
    Execute an LLM chat completion with multi-tier, multi-key automatic failover.
    
    1. Orders endpoints based on `selected_model` or `use_llm2_model`.
    2. Sequentially tries each candidate endpoint/key in the pool.
    3. Seamlessly fails over on HTTP errors (400, 401, 403, 429, 500, 503), timeouts, or empty responses.
    4. Returns the trimmed response string from the first successful endpoint.
    """
    configured = list(endpoints) if endpoints is not None else get_configured_endpoints()
    
    if not configured:
        # Fallback to minimal endpoint from raw env
        k = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
        m = selected_model or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
        u = os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1"
        configured = [LLMEndpoint(name="Default Raw", model=m, base_url=u, api_key=k)]

    # Determine candidate order
    candidates: List[LLMEndpoint] = []
    
    if selected_model:
        # Find matching model endpoints across all tiers/keys
        matched = [ep for ep in configured if ep.model == selected_model]
        unmatched = [ep for ep in configured if ep.model != selected_model]
        
        if matched:
            candidates.extend(matched)
        else:
            # Create ad-hoc endpoint with selected_model on primary base_url
            primary_ep = configured[0]
            candidates.append(LLMEndpoint(
                name=f"Selected ({selected_model})",
                model=selected_model,
                base_url=primary_ep.base_url,
                api_key=primary_ep.api_key,
                timeout=primary_ep.timeout
            ))
        candidates.extend(unmatched)
        
    elif use_llm2_model:
        # Prioritize LLM2 endpoint(s) if present
        llm2_eps = [ep for ep in configured if ep.name.startswith("LLM2")]
        other_eps = [ep for ep in configured if not ep.name.startswith("LLM2")]
        candidates = llm2_eps + other_eps if llm2_eps else configured
    else:
        candidates = configured

    # Try each candidate in sequence
    last_error = None
    for idx, candidate in enumerate(candidates):
        try:
            print(f"[LLM] Calling candidate #{idx + 1} '{candidate.name}' (Model: {candidate.model}, Base URL: {candidate.clean_base_url})...")
            content = _execute_chat_completion(
                endpoint=candidate,
                prompt=prompt,
                additional_messages=additional_messages,
                timeout=timeout
            )
            
            if content:
                if idx > 0:
                    print(f"[LLM Fallback SUCCESS] ✅ Failover to #{idx + 1} '{candidate.name}' ({candidate.model}) succeeded!")
                return content
            else:
                print(f"[LLM Fallback] ⚠️ Candidate '{candidate.name}' returned empty text. Trying next fallback...")
                
        except requests.exceptions.RequestException as req_err:
            status_code = getattr(getattr(req_err, 'response', None), 'status_code', 'N/A')
            err_msg = str(req_err)
            # Avoid leaking secrets in exception messages
            if candidate.api_key and candidate.api_key in err_msg:
                err_msg = err_msg.replace(candidate.api_key, "[REDACTED]")
            print(f"[LLM Fallback] ⚠️ Candidate #{idx + 1} '{candidate.name}' failed (HTTP {status_code}: {err_msg}). Failing over to next LLM...")
            last_error = req_err
        except Exception as gen_err:
            err_msg = str(gen_err)
            if candidate.api_key and candidate.api_key in err_msg:
                err_msg = err_msg.replace(candidate.api_key, "[REDACTED]")
            print(f"[LLM Fallback] ⚠️ Candidate #{idx + 1} '{candidate.name}' exception: {err_msg}. Failing over to next LLM...")
            last_error = gen_err

    print(f"[LLM CRITICAL] ❌ All {len(candidates)} LLM candidate(s) failed. Last error: {last_error}")
    return ""
