"""Environment-backed application settings, shared MongoDB pool, and bot profile helpers."""

from dataclasses import dataclass
import os
import threading
from typing import Any

_mongo_lock = threading.Lock()
_mongo_clients: dict[tuple[str, int], Any] = {}


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


def get_mongo_client(mongo_uri: str | None = None, timeout_ms: int | None = None) -> Any:
    """Return a shared MongoClient for the given URI/timeout, or None if mongo_uri is empty."""
    uri = (os.environ.get("MONGO_URI", "") if mongo_uri is None else mongo_uri).strip()
    if not uri:
        return None
    resolved_timeout = int(os.environ.get("MONGO_TIMEOUT_MS", "5000")) if timeout_ms is None else int(timeout_ms)
    cache_key = (uri, resolved_timeout)
    with _mongo_lock:
        client = _mongo_clients.get(cache_key)
        if client is None:
            from pymongo import MongoClient

            client = MongoClient(
                uri,
                serverSelectionTimeoutMS=resolved_timeout,
                connectTimeoutMS=resolved_timeout,
                socketTimeoutMS=resolved_timeout,
            )
            _mongo_clients[cache_key] = client
        return client


def get_admin_users() -> frozenset[str]:
    """Return Telegram user IDs configured in ADMIN_USERS (empty if unset)."""
    raw = os.environ.get("ADMIN_USERS", "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def is_admin_user(telegram_id: str | int) -> bool:
    """Check whether telegram_id is allowed to invoke privileged owner/admin commands."""
    admins = get_admin_users()
    if admins:
        return str(telegram_id).strip() in admins
    # Backward-compatible fallback: if ALLOWED_USERS is explicitly configured, treat it as private bot allowlist
    allowed_raw = os.environ.get("ALLOWED_USERS", "")
    allowed = [item.strip() for item in allowed_raw.split(",") if item.strip()]
    if allowed:
        return str(telegram_id).strip() in allowed
    # Public mode with neither ADMIN_USERS nor ALLOWED_USERS blocks privileged owner assets by default
    return os.environ.get("PUBLIC_ALLOW_PRIVILEGED_COMMANDS", "").strip().lower() in ("1", "true", "yes", "on")


def get_bot_display_name() -> str:
    return (os.environ.get("BOT_DISPLAY_NAME") or "Oli 333 - Summary & AI Bot").strip()


def get_bot_tagline() -> str:
    return (os.environ.get("BOT_TAGLINE") or "✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡").strip()


def get_support_contact() -> str:
    return (os.environ.get("SUPPORT_CONTACT") or "the bot administrator").strip()


def get_data_dir() -> str:
    """Return persistent data directory if configured or mounted at /app/data."""
    env_dir = os.environ.get("BOT_DATA_DIR", "").strip()
    if env_dir:
        return env_dir
    if os.path.isdir("/app/data"):
        return "/app/data"
    return ""
