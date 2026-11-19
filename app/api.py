import os
import secrets
import logging
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
)

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("summary_api")

app = FastAPI(
    title="Oli Summary API",
    description="API for summarizing web page content, YouTube transcripts, or general text.",
    version="1.0.0"
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

security = HTTPBearer()

# Read valid tokens from environment variables
API_AUTH_TOKENS = os.environ.get("API_AUTH_TOKENS", os.environ.get("API_AUTH_TOKEN", ""))
valid_tokens = set(t.strip() for t in API_AUTH_TOKENS.split(",") if t.strip())

if not valid_tokens:
    # Generate an ephemeral secure random token
    ephemeral_token = secrets.token_hex(16)
    valid_tokens.add(ephemeral_token)
    logger.warning(
        f"⚠️ No API authentication tokens found in environment (API_AUTH_TOKENS or API_AUTH_TOKEN). "
        f"Generated ephemeral token: {ephemeral_token}"
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
            return token
        if is_candidate_dynamic_api_key(token):
            try:
                is_valid = await run_blocking(verify_user_api_key, token)
            except Exception as exc:
                logger.error("API key verification failed due to backend error: %s", exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="API key verification service temporarily unavailable.",
                )
            if is_valid:
                _record_trusted_request_host(request)
                return token
    logger.warning("Unauthorized API access attempt with invalid token.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API token."
    )

class SummarizeRequest(BaseModel):
    input: str = Field(..., description="The YouTube URL, website URL, or text to summarize.", min_length=1, max_length=1_000_000)
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

@app.post("/api/v1/summarize", response_model=SummarizeResponse)
async def api_summarize(request: SummarizeRequest, token: str = Depends(verify_token)):
    from app.services.content import (
        is_url,
        is_safe_url,
        is_valid_raw_title,
        is_summary_error_message,
        sanitize_raw_title,
        resolve_final_title,
        parse_url_and_user_note,
        format_user_note_block,
    )

    user_input = request.input.strip()
    language = request.language.strip()
    selected_model = request.model
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
            detail="Invalid, blocked, or prohibited private/internal URL."
        )

    from app.legacy import process_user_input, summarize, get_web_title

    logger.info(f"Received summary request. Input length: {len(user_input)}, Lang: {language}")

    try:
        # 1. Process the input (fetch website, get youtube transcript, or split text)
        text_array = await run_blocking(process_user_input, user_input)

        error_msgs = [
            "暫時無法轉錄",
            "該影片沒有可用的字幕，且音頻轉換功能未啟用。",
            "無法獲取字幕或進行音頻轉換。",
            "音頻轉錄失敗。",
            "無法從 Pocket Casts 頁面提取 RSS feed。",
            "無法從 RSS feed 獲取 podcast episodes。",
            "處理 Pocket Casts URL 時發生錯誤。",
            "無法從 SoundOn 頁面提取 RSS feed。",
            "處理 SoundOn URL 時發生錯誤。",
            "無法從 Apple Podcast 提取 RSS feed。",
            "處理 Apple Podcast URL 時發生錯誤。",
            "Podcast 音頻轉錄失敗。"
        ]

        if isinstance(text_array, tuple):
            if len(text_array) == 2 and not text_array[0]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Content extraction failed: {text_array[1]}"
                )
            else:
                text_array = text_array[0]

        if isinstance(text_array, list) and len(text_array) == 1 and text_array[0] in error_msgs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Content extraction failed: {text_array[0]}"
            )

        if not text_array:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract any content from input."
            )

        # 2. Check ad filter via Clef decision model
        from app.services.decision import is_decision_ad_filter_enabled, is_advertisement_content
        if is_decision_ad_filter_enabled():
            is_ad, decision_data = await run_blocking(
                is_advertisement_content,
                text_array,
                url=user_input if is_url_input else None,
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

        # 3. Determine raw title and summarize the text array
        if is_url_input:
            original_url = user_input
            raw_title = await run_blocking(get_web_title, user_input, False)
        else:
            original_url = None
            raw_title = None

        summarize_result = await run_blocking(summarize, text_array, language=language, selected_model=selected_model, raw_title=raw_title, return_title=True, user_note=effective_note)
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

        return SummarizeResponse(
            status="success",
            title=title,
            original_title=sanitize_raw_title(raw_title) if is_valid_raw_title(raw_title) else None,
            original_url=original_url,
            summary=summary
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in api_summarize: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your summary request. Please try again later."
        )
