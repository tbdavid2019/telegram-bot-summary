"""Multi-tier LLM Service with automatic failover and multi-provider fallback.

Supports:
- Primary LLM (LLM_API_KEY, LLM_MODEL, LLM_BASE_URL)
- Secondary & Multi-tier LLMs (LLM2..LLM10)
- Auto Groq Fallback (GROQ_API_KEY)
- Model-level Fallbacks (LLM_FALLBACK_MODELS)
- Intelligent model name normalization (e.g. Google Gemini OpenAI endpoint formatting)
- Automatic retry on HTTP 4xx/5xx errors, timeouts, rate limits, and network errors.
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
    """Represents a configured LLM provider endpoint."""
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


def get_configured_endpoints() -> List[LLMEndpoint]:
    """
    Discover all configured LLM endpoints from environment variables in priority order:
    1. Primary (LLM_API_KEY / LLM_MODEL / LLM_BASE_URL)
    2. LLM2 (LLM2_API_KEY / LLM2_MODEL / LLM2_BASE_URL)
    3. LLM3..LLM10 (LLM{i}_API_KEY / LLM{i}_MODEL / LLM{i}_BASE_URL)
    4. Auto Groq fallback (if GROQ_API_KEY is available and not already configured)
    """
    timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
    endpoints: List[LLMEndpoint] = []

    # 1. Primary LLM
    primary_key = os.environ.get("LLM_API_KEY") or os.environ.get("LLM1_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    primary_model = os.environ.get("LLM_MODEL") or os.environ.get("LLM1_MODEL") or "gpt-4o-mini"
    primary_base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("LLM1_BASE_URL") or "https://api.openai.com/v1"

    if primary_key and primary_key.strip() and primary_key != "YOUR_API_KEY":
        endpoints.append(LLMEndpoint(
            name="LLM1 (Primary)",
            model=primary_model.strip(),
            base_url=primary_base_url.strip(),
            api_key=primary_key.strip(),
            timeout=timeout,
        ))

    # 2. LLM2..LLM10
    for idx in range(2, 11):
        k = os.environ.get(f"LLM{idx}_API_KEY", "").strip()
        m = os.environ.get(f"LLM{idx}_MODEL", "").strip()
        u = os.environ.get(f"LLM{idx}_BASE_URL", "").strip()

        # If base_url is omitted but Groq key is used or standard OpenAI
        if not u and (m.startswith("llama") or m.startswith("gemma") or m.startswith("openai/gpt-oss") or "groq" in k.lower()):
            u = "https://api.groq.com/openai/v1"
        elif not u:
            u = "https://api.openai.com/v1"

        if k and m and k != "YOUR_API_KEY":
            endpoints.append(LLMEndpoint(
                name=f"LLM{idx}",
                model=m,
                base_url=u,
                api_key=k,
                timeout=timeout,
            ))

    # 3. Model fallbacks on Primary endpoint if LLM_FALLBACK_MODELS is set
    fallback_models_env = os.environ.get("LLM_FALLBACK_MODELS", "").strip()
    if fallback_models_env and primary_key and primary_key != "YOUR_API_KEY":
        for fb_model in [m.strip() for m in fallback_models_env.split(",") if m.strip()]:
            if not any(ep.model == fb_model and ep.clean_base_url == primary_base_url.rstrip("/") for ep in endpoints):
                endpoints.append(LLMEndpoint(
                    name=f"Primary Fallback ({fb_model})",
                    model=fb_model,
                    base_url=primary_base_url.strip(),
                    api_key=primary_key.strip(),
                    timeout=timeout,
                ))

    # 4. Auto Groq fallback if GROQ_API_KEY is present and not yet in endpoints
    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key and groq_key != "YOUR_GROQ_API_KEY" and not any("groq.com" in ep.base_url for ep in endpoints):
        groq_model = os.environ.get("GROQ_FALLBACK_MODEL", "llama-3.3-70b-versatile")
        endpoints.append(LLMEndpoint(
            name=f"Groq Auto-Fallback ({groq_model})",
            model=groq_model,
            base_url="https://api.groq.com/openai/v1",
            api_key=groq_key,
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
        # Google Gemini OpenAI-compatible endpoint expects 'gemini-1.5-flash' rather than 'models/gemini-flash-latest'
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
    Send a single POST request to the LLM endpoint's /chat/completions.
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
    
    data = {
        "model": target_model,
        "messages": messages,
    }
    
    req_timeout = timeout or endpoint.timeout
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


def call_llm_with_fallback(
    prompt: str,
    additional_messages: Optional[List[Dict[str, str]]] = None,
    use_llm2_model: bool = False,
    selected_model: Optional[str] = None,
    timeout: Optional[float] = None,
    endpoints: Optional[List[LLMEndpoint]] = None
) -> str:
    """
    Execute an LLM chat completion with multi-tier automatic failover.
    
    1. Orders endpoints based on `selected_model` or `use_llm2_model`.
    2. Sequentially tries each endpoint in the candidate list.
    3. Seamlessly fails over on HTTP errors (400, 429, 500, 503, etc.), timeouts, or empty responses.
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
        # Find exact matching model endpoint
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
        # Prioritize LLM2 endpoint if present
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

    print(f"[LLM CRITICAL] ❌ All {len(candidates)} LLM endpoint(s) failed. Last error: {last_error}")
    return ""
