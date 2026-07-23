"""Environment-backed application settings."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    mongo_uri: str
    llm_api_key: str
    llm_model: str
    llm_base_url: str
    web_request_timeout_seconds: float
    llm_timeout_seconds: float
    asr_timeout_seconds: float
    media_download_timeout_seconds: float
    mongo_timeout_ms: int

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            telegram_token=os.environ.get("TELEGRAM_TOKEN", "xxx"),
            mongo_uri=os.environ.get("MONGO_URI", ""),
            llm_api_key=os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY")),
            llm_model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            web_request_timeout_seconds=float(
                os.environ.get("WEB_REQUEST_TIMEOUT_SECONDS", os.environ.get("HTTP_TIMEOUT_SECONDS", "60"))
            ),
            llm_timeout_seconds=float(os.environ.get("LLM_TIMEOUT_SECONDS", "180")),
            asr_timeout_seconds=float(
                os.environ.get("ASR_TIMEOUT_SECONDS", os.environ.get("SUBPROCESS_TIMEOUT_SECONDS", "600"))
            ),
            media_download_timeout_seconds=float(os.environ.get("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "900")),
            mongo_timeout_ms=int(os.environ.get("MONGO_TIMEOUT_MS", "5000")),
        )
