from collections import deque
import asyncio
import hashlib
import logging
import os
import secrets
import threading
import time
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from app.runtime import run_blocking
from app.services.api_keys import (
    is_candidate_dynamic_api_key,
    is_proxy_headers_trusted,
    record_observed_base_url,
    verify_user_api_key,
    verify_user_api_key_owner,
)

_ORIG_VERIFY_USER_API_KEY = verify_user_api_key

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("summary_api")

app = FastAPI(
    title="Oli Summary API",
    description="API for summarizing web page content, YouTube transcripts, or general text.",
    version="1.0.0",
)

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}
_BOT_READY = False
_SUMMARY_SEMAPHORE: asyncio.Semaphore | None = None
_SUMMARY_SEMAPHORE_LOOP_ID: int | None = None


def _get_summary_semaphore() -> asyncio.Semaphore:
    global _SUMMARY_SEMAPHORE, _SUMMARY_SEMAPHORE_LOOP_ID
    loop = asyncio.get_running_loop()
    loop_id = id(loop)
    if _SUMMARY_SEMAPHORE is None or _SUMMARY_SEMAPHORE_LOOP_ID != loop_id:
        limit = max(1, int(os.environ.get("API_MAX_CONCURRENT_SUMMARIES", "4")))
        _SUMMARY_SEMAPHORE = asyncio.Semaphore(limit)
        _SUMMARY_SEMAPHORE_LOOP_ID = loop_id
    return _SUMMARY_SEMAPHORE


def set_bot_ready(ready: bool) -> None:
    global _BOT_READY
    _BOT_READY = bool(ready)


def _check_rate_limit(actor_key: str, limit: int | None = None) -> None:
    resolved_limit = int(os.environ.get("API_RATE_LIMIT_PER_MINUTE", "30")) if limit is None else int(limit)
    if resolved_limit <= 0:
        return
    now = time.monotonic()
    cutoff = now - 60.0
    with _RATE_LIMIT_LOCK:
        if len(_RATE_LIMIT_BUCKETS) > 1000:
            stale = [k for k, dq in _RATE_LIMIT_BUCKETS.items() if not dq or dq[-1] < cutoff]
            for k in stale:
                _RATE_LIMIT_BUCKETS.pop(k, None)
        bucket = _RATE_LIMIT_BUCKETS.setdefault(actor_key, deque())
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= resolved_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before retrying.",
            )
        bucket.append(now)


def _get_client_ip(request: Request) -> str:
    if is_proxy_headers_trusted():
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


security = HTTPBearer()

# Read valid tokens from environment variables
API_AUTH_TOKENS = os.environ.get("API_AUTH_TOKENS", os.environ.get("API_AUTH_TOKEN", ""))
valid_tokens = set(t.strip() for t in API_AUTH_TOKENS.split(",") if t.strip())

if not valid_tokens:
    ephemeral_token = secrets.token_hex(16)
    valid_tokens.add(ephemeral_token)
    logger.warning(
        "⚠️ No API authentication tokens found in environment (API_AUTH_TOKENS or API_AUTH_TOKEN). "
        "Generated internal ephemeral token for this process (redacted from logs; set API_AUTH_TOKENS or use /apikey)."
    )


def _record_trusted_request_host(request: Request) -> None:
    if is_proxy_headers_trusted():
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        scheme = forwarded_proto.split(",")[0].strip() if forwarded_proto else request.url.scheme
        forwarded_host = request.headers.get("x-forwarded-host", "")
        host = forwarded_host.split(",")[0].strip() if forwarded_host else request.headers.get("host", "")
    else:
        scheme = request.url.scheme
        host = request.headers.get("host", "")
    if scheme and host:
        record_observed_base_url(scheme, host)


async def verify_token(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials if credentials else ""
    if token:
        token_bytes = token.encode("utf-8")
        if any(secrets.compare_digest(token_bytes, valid_t.encode("utf-8")) for valid_t in valid_tokens):
            _record_trusted_request_host(request)
            actor_id = f"static:{hashlib.sha256(token_bytes).hexdigest()[:12]}"
            request.state.api_owner_id = actor_id
            _check_rate_limit(actor_id)
            return token

        preauth_limit = int(os.environ.get("API_PREAUTH_RATE_LIMIT_PER_MINUTE", "60"))
        _check_rate_limit(f"preauth:{_get_client_ip(request)}", limit=preauth_limit)

        if is_candidate_dynamic_api_key(token):
            owner_id: str | None = None
            try:
                if verify_user_api_key is _ORIG_VERIFY_USER_API_KEY:
                    owner_id = await run_blocking(verify_user_api_key_owner, token)
                    is_valid = owner_id is not None
                else:
                    is_valid = bool(await run_blocking(verify_user_api_key, token))
            except Exception as exc:
                logger.error("API key verification failed due to backend error: %s", exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="API key verification service temporarily unavailable.",
                )
            if is_valid:
                _record_trusted_request_host(request)
                actor_id = f"owner:{owner_id}" if owner_id else f"dyn:{hashlib.sha256(token_bytes).hexdigest()[:12]}"
                request.state.api_owner_id = actor_id
                _check_rate_limit(actor_id)
                return token
    else:
        preauth_limit = int(os.environ.get("API_PREAUTH_RATE_LIMIT_PER_MINUTE", "60"))
        _check_rate_limit(f"preauth:{_get_client_ip(request)}", limit=preauth_limit)

    logger.warning("Unauthorized API access attempt with invalid token.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API token.",
    )


class SummarizeRequest(BaseModel):
    input: str = Field(..., description="The YouTube URL, website URL, or text to summarize.", min_length=1, max_length=200_000)
    language: str = Field("zh-TW", description="The output summary language (e.g. 'zh-TW', 'en').", max_length=50)
    model: Optional[str] = Field(None, description="Optional custom LLM model override.", max_length=100)
    user_note: Optional[str] = Field(None, description="Optional personal note, commentary, or questions to prepend and address in the summary.", max_length=4000)


class SummarizeResponse(BaseModel):
    status: str = Field("success", description="Response status.")
    title: str = Field(..., description="The resolved title of the content.")
    original_title: Optional[str] = Field(None, description="The original raw title before SEO optimization.")
    original_url: Optional[str] = Field(None, description="The original URL if the input was a URL.")
    summary: str = Field(..., description="The Markdown-formatted summary.")
    is_ad: bool = Field(False, description="Whether the content was flagged as an advertisement or promotional spam.")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/readyz")
def readiness_check():
    from app.config import get_mongo_client

    if not _BOT_READY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not ready yet.",
        )

    mongo_status = "disabled"
    mongo_uri = os.environ.get("MONGO_URI", "").strip()
    if mongo_uri:
        try:
            client = get_mongo_client(mongo_uri)
            client.admin.command("ping")
            mongo_status = "ok"
        except Exception as exc:
            logger.warning("Readiness MongoDB ping failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MongoDB readiness check failed.",
            )
    return {"status": "ready", "bot_ready": True, "mongodb": mongo_status}


@app.post("/api/v1/summarize", response_model=SummarizeResponse)
async def api_summarize(request: SummarizeRequest, http_request: Request, token: str = Depends(verify_token)):
    from app.services.content import (
        is_url,
        is_safe_url,
        is_valid_raw_title,
        is_summary_error_message,
        is_extraction_error,
        sanitize_raw_title,
        resolve_final_title,
        parse_url_and_user_note,
        format_user_note_block,
    )

    user_input = request.input.strip()
    language = request.language.strip()
    selected_model = request.model.strip() if isinstance(request.model, str) and request.model.strip() else None
    extracted_url, inline_note = await run_blocking(parse_url_and_user_note, user_input)
    if extracted_url:
        user_input = extracted_url

    explicit_note = request.user_note.strip() if isinstance(request.user_note, str) and request.user_note.strip() else None
    if explicit_note and inline_note and explicit_note != inline_note:
        sep = "\n\n"
        total_budget = 4000
        if len(explicit_note) + len(sep) + len(inline_note) <= total_budget:
            effective_note = f"{explicit_note}{sep}{inline_note}"
        else:
            explicit_part = explicit_note[:3000].rstrip()
            remaining_budget = total_budget - len(explicit_part) - len(sep)
            if remaining_budget > 0:
                inline_part = inline_note[:remaining_budget].rstrip()
                effective_note = f"{explicit_part}{sep}{inline_part}" if inline_part else explicit_part
            else:
                effective_note = explicit_note[:total_budget]
    else:
        effective_note = explicit_note or inline_note
        if effective_note and len(effective_note) > 4000:
            effective_note = effective_note[:4000]

    is_url_input = is_url(user_input)

    if is_url_input and not await run_blocking(is_safe_url, user_input):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, blocked, or prohibited private/internal URL.",
        )

    import sys
    from app.legacy import process_user_input, summarize, get_web_title

    legacy_mod = sys.modules.get("app.legacy")
    decision_collection = getattr(legacy_mod, "decision_collection", None) if legacy_mod is not None else None
    save_summary = getattr(legacy_mod, "save_summary", None) if legacy_mod is not None else None

    actor_id = getattr(http_request.state, "api_owner_id", "unknown")
    logger.info(
        "Received summary request. Actor: %s, Input length: %d, Lang: %s",
        actor_id,
        len(user_input),
        language,
    )

    try:
        sem = _get_summary_semaphore()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=1.0)
        except TimeoutError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Server busy processing concurrent summarization requests; please retry shortly.",
            )
        try:
            text_array = await run_blocking(process_user_input, user_input)

            if isinstance(text_array, tuple):
                if len(text_array) == 2 and not text_array[0]:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Content extraction failed: {text_array[1]}",
                    )
                text_array = text_array[0]

            if is_extraction_error(text_array):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content extraction failed: {text_array[0]}",
                )

            if not text_array:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Could not extract any content from input.",
                )

            from app.services.decision import is_decision_ad_filter_enabled, is_advertisement_content

            if is_decision_ad_filter_enabled():
                is_ad, _decision_data = await run_blocking(
                    is_advertisement_content,
                    text_array,
                    url=user_input if is_url_input else None,
                    mongo_collection=decision_collection,
                )
                if is_ad:
                    raw_title = await run_blocking(get_web_title, user_input, False) if is_url_input else None
                    title = resolve_final_title(None, raw_title, language, "Text Summary")
                    return SummarizeResponse(
                        status="hidden",
                        title=title,
                        original_title=sanitize_raw_title(raw_title) if is_valid_raw_title(raw_title) else None,
                        original_url=user_input if is_url_input else None,
                        summary="🚫 內容已隱藏：經 Clef 決策模型判定為商業廣告或垃圾行銷訊息。",
                        is_ad=True,
                    )

            if is_url_input:
                original_url = user_input
                raw_title = await run_blocking(get_web_title, user_input, False)
            else:
                original_url = None
                raw_title = None

            summarize_result = await run_blocking(
                summarize,
                text_array,
                language=language,
                selected_model=selected_model,
                raw_title=raw_title,
                return_title=True,
                user_note=effective_note,
            )
            if isinstance(summarize_result, tuple) and len(summarize_result) == 2:
                summary, ai_title = summarize_result
            else:
                summary, ai_title = summarize_result, None

            if is_summary_error_message(summary):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=summary,
                )

            note_block = format_user_note_block(effective_note)
            if note_block:
                summary = f"{note_block}\n\n---\n\n{summary}"

            title = resolve_final_title(ai_title, raw_title, language, "Text Summary")

            if callable(save_summary):
                from datetime import datetime

                summary_data = {
                    "api_actor": actor_id,
                    "url": original_url,
                    "title": title,
                    "original_title": raw_title,
                    "user_note": effective_note,
                    "summary": summary,
                    "original_content": text_array,
                    "language": language,
                    "timestamp": datetime.now(),
                }
                await run_blocking(save_summary, summary_data)

            return SummarizeResponse(
                status="success",
                title=title,
                original_title=sanitize_raw_title(raw_title) if is_valid_raw_title(raw_title) else None,
                original_url=original_url,
                summary=summary,
            )
        finally:
            sem.release()

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in api_summarize: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your summary request. Please try again later.",
        )
