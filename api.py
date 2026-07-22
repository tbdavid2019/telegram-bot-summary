import os
import secrets
import logging
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("summary_api")

app = FastAPI(
    title="Oli Summary API",
    description="API for summarizing web page content, YouTube transcripts, or general text.",
    version="1.0.0"
)

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

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if token not in valid_tokens:
        logger.warning("Unauthorized API access attempt with invalid token.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API token."
        )
    return token

class SummarizeRequest(BaseModel):
    input: str = Field(..., description="The YouTube URL, website URL, or text to summarize.", min_length=1)
    language: str = Field("zh-TW", description="The output summary language (e.g. 'zh-TW', 'en').")
    model: Optional[str] = Field(None, description="Optional custom LLM model override.")

class SummarizeResponse(BaseModel):
    status: str = Field("success", description="Response status.")
    title: str = Field(..., description="The resolved title of the content.")
    original_url: Optional[str] = Field(None, description="The original URL if the input was a URL.")
    summary: str = Field(..., description="The Markdown-formatted summary.")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/v1/summarize", response_model=SummarizeResponse)
async def api_summarize(request: SummarizeRequest, token: str = Depends(verify_token)):
    # Import core business logic from main to prevent top-level circular imports
    from main import process_user_input, summarize, is_url, get_web_title
    
    user_input = request.input.strip()
    language = request.language.strip()
    selected_model = request.model
    
    logger.info(f"Received summary request. Input length: {len(user_input)}, Lang: {language}")
    
    try:
        # 1. Process the input (fetch website, get youtube transcript, or split text)
        text_array = process_user_input(user_input)
        
        # Check if returned error message array
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
        
        # Handle scrape_text_from_url returning (text_array, error)
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
            
        # 2. Summarize the text array
        summary = summarize(text_array, language=language, selected_model=selected_model)
        
        # 3. Determine title and original url
        if is_url(user_input):
            original_url = user_input
            title = get_web_title(user_input)
        else:
            original_url = None
            title = "Text Summary"
            
        return SummarizeResponse(
            status="success",
            title=title,
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
