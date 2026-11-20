"""Per-user single API key management with bot-scope isolation and 4-layer base URL detection."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import shlex
import tempfile
import threading
import time
from typing import Any, Iterator, Optional
import urllib.parse

import requests

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

KEY_PREFIX = "oli_"
DEFAULT_API_PORT = 8001
_CANDIDATE_KEY_RE = re.compile(r"^oli_[A-Za-z0-9_-]{16,124}$")
_PUBLIC_IP_CACHE_TTL_SECONDS = 3600.0
_PUBLIC_IP_FAIL_CACHE_TTL_SECONDS = 60.0
_PUBLIC_IP_ENDPOINTS = (
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
)
_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
    "0.0.0.0",
})
_BLOCKED_HOST_SUFFIXES = (".local", ".localhost", ".internal", ".localdomain")
_FORBIDDEN_HOST_CHARS = frozenset("/\\@;,?#")
_FORBIDDEN_URL_CHARS = frozenset("'\"`")
_DOMAIN_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

_base_url_lock = threading.Lock()
_observed_base_url: Optional[str] = None
_public_ip_cache: Optional[tuple[float, Optional[str]]] = None

_manager_lock = threading.Lock()
_default_manager: Optional["APIKeyManager"] = None


class KeyAlreadyExistsError(ValueError):
    """Raised when attempting to create a second API key for the same (bot_scope, telegram_id)."""


class KeyNotFoundError(ValueError):
    """Raised when rotating an API key for a user that has no active key."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_bot_scope(telegram_token: str | None = None) -> str:
    """Derive a 12-char SHA-256 scope identifier from TELEGRAM_TOKEN without exposing it."""
    raw = os.environ.get("TELEGRAM_TOKEN", "") if telegram_token is None else telegram_token
    if not isinstance(raw, str):
        logger.warning(
            "TELEGRAM_TOKEN is not set; using 'default' bot_scope. "
            "Configure TELEGRAM_TOKEN to isolate API keys across bots."
        )
        return "default"
    token_clean = raw.strip()
    if not token_clean:
        logger.warning(
            "TELEGRAM_TOKEN is empty; using 'default' bot_scope. "
            "Configure TELEGRAM_TOKEN to isolate API keys across bots."
        )
        return "default"
    return hashlib.sha256(token_clean.encode("utf-8")).hexdigest()[:12]


def is_telegram_user_allowed(
    telegram_id: str | int,
    allowed_users_env: str | None = None,
) -> bool:
    """Return True if ALLOWED_USERS is empty or contains telegram_id."""
    raw = os.environ.get("ALLOWED_USERS", "") if allowed_users_env is None else allowed_users_env
    allowed_list = [u.strip() for u in raw.split(",") if u.strip()] if isinstance(raw, str) and raw else []
    if not allowed_list:
        return True
    tg_id = str(telegram_id).strip()
    return bool(tg_id and tg_id in allowed_list)


def get_trusted_hosts() -> frozenset[str]:
    """Return lowercase trusted hostnames (without port) from API_TRUSTED_HOSTS."""
    raw = os.environ.get("API_TRUSTED_HOSTS", "")
    if not raw:
        return frozenset()
    return frozenset(item.strip().lower() for item in raw.split(",") if item.strip())


def is_proxy_headers_trusted() -> bool:
    """Return whether X-Forwarded-* headers should be trusted."""
    return os.environ.get("API_TRUST_PROXY_HEADERS", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def generate_api_key() -> str:
    """Generate a high-entropy API key with the oli_ prefix."""
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of an API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def mask_api_key(prefix: str, suffix: str) -> str:
    """Format a masked key representation such as oli_AbCd...xYz9."""
    return f"{prefix}...{suffix}"


def is_candidate_dynamic_api_key(raw_key: str) -> bool:
    """Fast format pre-filter for dynamic oli_ bearer tokens before hitting storage."""
    if not isinstance(raw_key, str):
        return False
    return bool(_CANDIDATE_KEY_RE.fullmatch(raw_key.strip()))


def _is_disallowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
        or not ip.is_global
    )


def _validate_port(port_str: str) -> bool:
    if not port_str or not port_str.isascii() or not port_str.isdigit():
        return False
    port = int(port_str)
    return 1 <= port <= 65535


def _parse_safe_port(raw_port: Any) -> int:
    """Parse an integer port in 1..65535, logging a warning and returning DEFAULT_API_PORT on invalid input."""
    if raw_port is None:
        return DEFAULT_API_PORT
    if isinstance(raw_port, bool):
        logger.warning("Invalid API_PORT %r; falling back to %d", raw_port, DEFAULT_API_PORT)
        return DEFAULT_API_PORT
    if isinstance(raw_port, int):
        if 1 <= raw_port <= 65535:
            return raw_port
        logger.warning("Invalid API_PORT %r; falling back to %d", raw_port, DEFAULT_API_PORT)
        return DEFAULT_API_PORT
    port_str = str(raw_port).strip()
    if not _validate_port(port_str):
        logger.warning("Invalid API_PORT %r; falling back to %d", raw_port, DEFAULT_API_PORT)
        return DEFAULT_API_PORT
    return int(port_str)


def _extract_valid_hostname(host: str) -> str | None:
    if not isinstance(host, str) or not host or len(host) > 255:
        return None
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 or ch in _FORBIDDEN_HOST_CHARS for ch in host):
        return None

    if host.startswith("["):
        end_idx = host.find("]")
        if end_idx == -1:
            return None
        hostname = host[1:end_idx]
        rest = host[end_idx + 1 :]
        if rest:
            if not rest.startswith(":") or not _validate_port(rest[1:]):
                return None
    else:
        colon_count = host.count(":")
        if colon_count > 1:
            return None
        if colon_count == 1:
            hostname, port_str = host.split(":", 1)
            if not _validate_port(port_str):
                return None
        else:
            hostname = host

    if not hostname:
        return None

    hostname_lower = hostname.lower()
    if hostname_lower in _BLOCKED_HOSTNAMES or hostname_lower.endswith(_BLOCKED_HOST_SUFFIXES):
        return None

    try:
        ip = ipaddress.ip_address(hostname)
        if _is_disallowed_ip(ip):
            return None
        return ip.compressed.lower()
    except ValueError:
        pass

    labels = hostname_lower.split(".")
    if len(labels) < 2:
        return None
    if not all(bool(label and _DOMAIN_LABEL_RE.match(label)) for label in labels):
        return None
    return hostname_lower


def record_observed_base_url(scheme: str, host: str) -> bool:
    """Validate and record an observed external URL only when hostname is in API_TRUSTED_HOSTS."""
    global _observed_base_url

    trusted_hosts = get_trusted_hosts()
    if not trusted_hosts:
        return False

    if not isinstance(scheme, str) or not scheme.strip():
        return False
    scheme_clean = scheme.split(",")[0].strip().lower()
    if scheme_clean not in ("http", "https"):
        return False

    hostname = _extract_valid_hostname(host)
    if hostname is None or hostname not in trusted_hosts:
        return False

    observed = f"{scheme_clean}://{host}"
    with _base_url_lock:
        _observed_base_url = observed
    return True


def detect_public_ip(timeout: float = 3.0) -> str | None:
    """Detect and cache the host's global public IP (1h on success, 60s on failure)."""
    global _public_ip_cache

    now = time.monotonic()
    with _base_url_lock:
        if _public_ip_cache is not None:
            expires_at, cached_ip = _public_ip_cache
            if now < expires_at:
                return cached_ip
            _public_ip_cache = None

    headers = {"User-Agent": "telegram-bot-summary/1.0"}
    for endpoint in _PUBLIC_IP_ENDPOINTS:
        try:
            response = requests.get(endpoint, timeout=timeout, headers=headers)
            if response.status_code != 200:
                continue
            candidate = response.text.strip()
            ip = ipaddress.ip_address(candidate)
            if _is_disallowed_ip(ip):
                continue
            formatted = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
            with _base_url_lock:
                _public_ip_cache = (time.monotonic() + _PUBLIC_IP_CACHE_TTL_SECONDS, formatted)
            return formatted
        except Exception as exc:
            logger.debug("Public IP lookup failed for %s: %s", endpoint, exc)
            continue

    with _base_url_lock:
        _public_ip_cache = (time.monotonic() + _PUBLIC_IP_FAIL_CACHE_TTL_SECONDS, None)
    return None


def _is_valid_public_env_url(raw_url: str) -> bool:
    if not isinstance(raw_url, str) or not raw_url:
        return False
    if any(
        ch.isspace() or ord(ch) < 32 or ord(ch) == 127 or ch in _FORBIDDEN_URL_CHARS
        for ch in raw_url
    ):
        return False
    try:
        parsed = urllib.parse.urlparse(raw_url)
    except Exception:
        return False

    if parsed.scheme.lower() not in ("http", "https"):
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if parsed.params or parsed.query or parsed.fragment:
        return False
    if not parsed.netloc or not parsed.hostname:
        return False

    try:
        port = parsed.port
    except ValueError:
        return False
    if port is not None and not (1 <= port <= 65535):
        return False

    hostname = parsed.hostname.lower()
    try:
        ipaddress.ip_address(hostname)
        return True
    except ValueError:
        pass

    labels = hostname.split(".")
    return all(bool(label and _DOMAIN_LABEL_RE.match(label)) for label in labels)


def resolve_api_base_url(api_port: int | None = None) -> tuple[str, str]:
    """Resolve the API base URL across 4 priority layers: env -> observed -> public_ip -> localhost."""
    if api_port is not None:
        port = _parse_safe_port(api_port)
    elif "API_PORT" in os.environ:
        port = _parse_safe_port(os.environ.get("API_PORT"))
    else:
        port = DEFAULT_API_PORT

    env_url = os.environ.get("API_PUBLIC_URL", "").strip().rstrip("/")
    if _is_valid_public_env_url(env_url):
        return (env_url, "env")

    with _base_url_lock:
        observed = _observed_base_url
    if observed:
        return (observed, "observed")

    public_ip = detect_public_ip()
    if public_ip:
        return (f"http://{public_ip}:{port}", "public_ip")

    return (f"http://localhost:{port}", "localhost")


def build_curl_usage_guide(base_url: str, api_key: str | None = None) -> str:
    """Format shell-safe cURL usage examples and response field notes."""
    clean_base = (base_url or "").strip().rstrip("/")
    token = api_key.strip() if isinstance(api_key, str) and api_key.strip() else "<YOUR_API_KEY>"

    health_url_arg = shlex.quote(f"{clean_base}/health")
    summarize_url_arg = shlex.quote(f"{clean_base}/api/v1/summarize")
    auth_header_arg = shlex.quote(f"Authorization: Bearer {token}")
    url_payload_arg = shlex.quote('{"input":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"zh-TW"}')
    text_payload_arg = shlex.quote('{"input":"這裡放你想摘要的文章內容...","language":"zh-TW"}')

    lines = [
        "1. 健康檢查：",
        f"curl -s {health_url_arg}",
        "",
        "2. 網址 / YouTube 摘要：",
        (
            f"curl -X POST {summarize_url_arg} "
            f"-H {auth_header_arg} "
            "-H 'Content-Type: application/json' "
            f"-d {url_payload_arg}"
        ),
        "",
        "3. 純文字摘要（可選指定語言與模型）：",
        (
            f"curl -X POST {summarize_url_arg} "
            f"-H {auth_header_arg} "
            "-H 'Content-Type: application/json' "
            f"-d {text_payload_arg}"
        ),
        "",
        "回傳 JSON 欄位說明：status, title（AI SEO 標題）, original_title, original_url, summary, is_ad",
    ]

    if clean_base.lower().startswith("http://"):
        lines.extend([
            "",
            "⚠️ 目前為 HTTP 端點，建議搭配 HTTPS 反向代理並於 .env 設定 API_PUBLIC_URL 以保護 Bearer Token。",
        ])

    return "\n".join(lines)


class APIKeyManager:
    """Manage one active API key per (bot_scope, telegram_id) without persisting plaintext keys."""

    def __init__(
        self,
        mongo_collection: Any = None,
        bot_scope: str | None = None,
        fallback_file: str | None = None,
        cache_ttl_seconds: float = 0.0,
    ) -> None:
        self.bot_scope = (
            bot_scope.strip()
            if isinstance(bot_scope, str) and bot_scope.strip()
            else get_bot_scope()
        )
        self.cache_ttl_seconds = float(cache_ttl_seconds)
        self._lock = threading.RLock()
        self._memory_store: dict[str, dict[str, Any]] = {}
        self._collection = mongo_collection

        if self._collection is None:
            mongo_uri = os.environ.get("MONGO_URI", "").strip()
            if mongo_uri:
                mongo_timeout_ms = int(os.environ.get("MONGO_TIMEOUT_MS", "5000"))
                from app.config import get_mongo_client

                client = get_mongo_client(mongo_uri, timeout_ms=mongo_timeout_ms)
                self._collection = client["bot_database"]["api_keys"]
                self._ensure_indexes()

        if fallback_file is not None:
            self.fallback_file = fallback_file.strip()
        else:
            env_file = os.environ.get("API_KEYS_FILE", "").strip()
            if env_file:
                self.fallback_file = env_file
            elif self._collection is None:
                from app.config import get_data_dir

                data_dir = get_data_dir()
                self.fallback_file = os.path.join(data_dir, "api_keys.json") if data_dir else ""
            else:
                self.fallback_file = ""

    def _ensure_indexes(self) -> None:
        if self._collection is None:
            return
        for keys in (
            [("bot_scope", 1), ("telegram_id", 1)],
            [("key_hash", 1)],
        ):
            try:
                self._collection.create_index(keys, unique=True)
            except Exception as exc:
                logger.warning("Failed to create MongoDB index %s on api_keys: %s", keys, exc)

    @staticmethod
    def _normalize_telegram_id(telegram_id: str | int) -> str:
        tg_id = str(telegram_id).strip()
        if not tg_id:
            raise ValueError("telegram_id must not be empty")
        return tg_id

    def _composite_key(self, tg_id: str) -> str:
        return f"{self.bot_scope}:{tg_id}"

    @contextmanager
    def _file_lock(self, exclusive: bool = False) -> Iterator[None]:
        if not self.fallback_file or fcntl is None:
            yield
            return

        abs_path = os.path.abspath(self.fallback_file)
        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        lock_path = f"{abs_path}.lock"
        lock_file = open(lock_path, "a+", encoding="utf-8")
        try:
            mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_file.fileno(), mode)
            yield
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            finally:
                lock_file.close()

    def _load_fallback_data(self) -> dict[str, dict[str, Any]]:
        if not self.fallback_file:
            return self._memory_store
        try:
            with open(self.fallback_file, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to read or parse API keys file %s: %s", self.fallback_file, exc)
            raise RuntimeError(f"Corrupted or unreadable API keys file: {self.fallback_file}") from exc

        if not isinstance(loaded, dict):
            logger.error("Invalid API keys storage structure in %s: expected JSON object", self.fallback_file)
            raise RuntimeError(f"Invalid API keys storage format in: {self.fallback_file}")
        return loaded

    def _save_fallback_data(self, data: dict[str, dict[str, Any]]) -> None:
        if not self.fallback_file:
            return
        abs_path = os.path.abspath(self.fallback_file)
        parent_dir = os.path.dirname(abs_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=parent_dir or ".",
                prefix=".api_keys_",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                tmp_path = tmp_file.name
                try:
                    os.chmod(tmp_path, 0o600)
                except OSError:
                    pass
                json.dump(data, tmp_file, ensure_ascii=False, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, abs_path)
        except Exception:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    def _find_by_user(self, tg_id: str) -> dict[str, Any] | None:
        comp_id = self._composite_key(tg_id)
        if self._collection is not None:
            return self._collection.find_one(
                {"_id": comp_id, "bot_scope": self.bot_scope, "telegram_id": tg_id}
            )
        with self._lock:
            with self._file_lock(exclusive=False):
                data = self._load_fallback_data()
                rec = data.get(comp_id)
                return dict(rec) if isinstance(rec, dict) else None

    def _find_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        if self._collection is not None:
            return self._collection.find_one({"bot_scope": self.bot_scope, "key_hash": key_hash})
        with self._lock:
            with self._file_lock(exclusive=False):
                data = self._load_fallback_data()
                for rec in data.values():
                    if (
                        isinstance(rec, dict)
                        and rec.get("bot_scope") == self.bot_scope
                        and rec.get("key_hash") == key_hash
                    ):
                        return dict(rec)
        return None

    def _build_record(
        self,
        tg_id: str,
        raw_key: str,
        created_at: str,
        rotated_at: str | None = None,
    ) -> dict[str, Any]:
        key_prefix = raw_key[:8]
        key_suffix = raw_key[-4:]
        return {
            "_id": self._composite_key(tg_id),
            "bot_scope": self.bot_scope,
            "telegram_id": tg_id,
            "key_hash": hash_api_key(raw_key),
            "key_prefix": key_prefix,
            "key_suffix": key_suffix,
            "masked_key": mask_api_key(key_prefix, key_suffix),
            "created_at": created_at,
            "rotated_at": rotated_at,
            "last_used_at": None,
        }

    def get_key_metadata(self, telegram_id: str | int) -> dict[str, Any] | None:
        """Return non-secret key metadata for a user in this bot_scope."""
        tg_id = self._normalize_telegram_id(telegram_id)
        doc = self._find_by_user(tg_id)
        if not doc:
            return None
        masked = doc.get("masked_key") or mask_api_key(
            doc.get("key_prefix", ""),
            doc.get("key_suffix", ""),
        )
        return {
            "telegram_id": str(doc.get("telegram_id", tg_id)),
            "masked_key": masked,
            "created_at": doc.get("created_at"),
            "rotated_at": doc.get("rotated_at"),
            "last_used_at": doc.get("last_used_at"),
        }

    def create_key(self, telegram_id: str | int) -> dict[str, Any]:
        """Atomically create the single allowed API key for (bot_scope, telegram_id)."""
        tg_id = self._normalize_telegram_id(telegram_id)
        raw_key = generate_api_key()
        now_iso = _utc_now_iso()
        doc = self._build_record(tg_id, raw_key, created_at=now_iso, rotated_at=None)

        if self._collection is not None:
            try:
                self._collection.insert_one(dict(doc))
            except Exception as exc:
                if "DuplicateKey" in type(exc).__name__ or "E11000" in str(exc):
                    raise KeyAlreadyExistsError(
                        "API key already exists for this user; use rotate_key instead."
                    ) from exc
                raise
        else:
            with self._lock:
                with self._file_lock(exclusive=True):
                    data = self._load_fallback_data()
                    comp_key = self._composite_key(tg_id)
                    if comp_key in data:
                        raise KeyAlreadyExistsError(
                            "API key already exists for this user; use rotate_key instead."
                        )
                    data[comp_key] = dict(doc)
                    self._save_fallback_data(data)

        return {
            "api_key": raw_key,
            "masked_key": doc["masked_key"],
            "created_at": now_iso,
            "rotated": False,
        }

    def rotate_key(self, telegram_id: str | int) -> dict[str, Any]:
        """Atomically rotate an existing user's API key; raise KeyNotFoundError if none exists."""
        tg_id = self._normalize_telegram_id(telegram_id)
        comp_id = self._composite_key(tg_id)
        raw_key = generate_api_key()
        now_iso = _utc_now_iso()

        if self._collection is not None:
            query = {"_id": comp_id, "bot_scope": self.bot_scope, "telegram_id": tg_id}
            existing = self._collection.find_one(query)
            if not isinstance(existing, dict):
                raise KeyNotFoundError("No active API key found for this user; create one first.")
            created_at = existing.get("created_at") or now_iso
            doc = self._build_record(tg_id, raw_key, created_at=created_at, rotated_at=now_iso)
            cas_query = dict(query)
            if isinstance(existing.get("key_hash"), str):
                cas_query["key_hash"] = existing["key_hash"]
            result = self._collection.replace_one(cas_query, dict(doc), upsert=False)
            if result is not None and getattr(result, "matched_count", 1) == 0:
                if self._collection.find_one(query) is not None:
                    raise RuntimeError("API key was rotated concurrently; please retry.")
                raise KeyNotFoundError("No active API key found for this user; create one first.")
        else:
            with self._lock:
                with self._file_lock(exclusive=True):
                    data = self._load_fallback_data()
                    existing = data.get(comp_id)
                    if not isinstance(existing, dict):
                        raise KeyNotFoundError("No active API key found for this user; create one first.")
                    created_at = existing.get("created_at") or now_iso
                    doc = self._build_record(tg_id, raw_key, created_at=created_at, rotated_at=now_iso)
                    data[comp_id] = dict(doc)
                    self._save_fallback_data(data)

        return {
            "api_key": raw_key,
            "masked_key": doc["masked_key"],
            "created_at": created_at,
            "rotated_at": now_iso,
            "rotated": True,
        }

    def revoke_key(self, telegram_id: str | int) -> bool:
        """Delete the user's API key in this bot_scope."""
        tg_id = self._normalize_telegram_id(telegram_id)
        comp_id = self._composite_key(tg_id)

        if self._collection is not None:
            result = self._collection.delete_one(
                {"_id": comp_id, "bot_scope": self.bot_scope, "telegram_id": tg_id}
            )
            return bool(getattr(result, "deleted_count", 0) > 0)

        with self._lock:
            with self._file_lock(exclusive=True):
                data = self._load_fallback_data()
                existing = data.pop(comp_id, None)
                if isinstance(existing, dict):
                    self._save_fallback_data(data)
                    return True
                return False

    def _update_last_used_best_effort(self, tg_id: str, key_hash: str) -> None:
        now_iso = _utc_now_iso()
        comp_id = self._composite_key(tg_id)
        try:
            if self._collection is not None:
                self._collection.update_one(
                    {"_id": comp_id, "bot_scope": self.bot_scope, "telegram_id": tg_id, "key_hash": key_hash},
                    {"$set": {"last_used_at": now_iso}},
                )
            else:
                with self._lock:
                    with self._file_lock(exclusive=True):
                        data = self._load_fallback_data()
                        rec = data.get(comp_id)
                        if isinstance(rec, dict) and rec.get("key_hash") == key_hash:
                            rec["last_used_at"] = now_iso
                            self._save_fallback_data(data)
        except Exception as exc:
            logger.debug("Best-effort last_used_at update failed: %s", exc)

    @staticmethod
    def _should_refresh_last_used(last_used_at: Any, min_interval_seconds: int = 60) -> bool:
        if not isinstance(last_used_at, str) or not last_used_at.strip():
            return True
        try:
            parsed = datetime.fromisoformat(last_used_at.strip().replace("Z", "+00:00"))
            elapsed = (datetime.now(timezone.utc) - parsed).total_seconds()
            return elapsed >= min_interval_seconds
        except Exception:
            return True

    def verify_key_owner(self, raw_key: str) -> str | None:
        """Authoritatively verify a raw key against storage and return its telegram_id or None."""
        if not is_candidate_dynamic_api_key(raw_key):
            return None

        candidate_hash = hash_api_key(raw_key.strip())
        doc = self._find_by_hash(candidate_hash)
        if not doc:
            return None

        stored_hash = doc.get("key_hash")
        if not isinstance(stored_hash, str) or not hmac.compare_digest(
            stored_hash.encode("utf-8"), candidate_hash.encode("utf-8")
        ):
            return None

        tg_id = str(doc.get("telegram_id", "")).strip()
        if not tg_id:
            return None

        if self._should_refresh_last_used(doc.get("last_used_at")):
            self._update_last_used_best_effort(tg_id, candidate_hash)
        return tg_id

    def verify_key(self, raw_key: str, enforce_allowed_users: bool = True) -> bool:
        """Verify a raw API key and optionally enforce the live ALLOWED_USERS allowlist."""
        owner_id = self.verify_key_owner(raw_key)
        if owner_id is None:
            return False
        if enforce_allowed_users and not is_telegram_user_allowed(owner_id):
            return False
        return True


def get_api_key_manager() -> APIKeyManager:
    """Return the process-wide lazy singleton APIKeyManager."""
    global _default_manager
    with _manager_lock:
        if _default_manager is None:
            _default_manager = APIKeyManager()
        return _default_manager


def verify_user_api_key_owner(raw_key: str) -> str | None:
    """Verify a dynamic user API key and return its allowed owner telegram_id, or None."""
    manager = get_api_key_manager()
    owner_id = manager.verify_key_owner(raw_key)
    if owner_id is None or not is_telegram_user_allowed(owner_id):
        return None
    return owner_id


def verify_user_api_key(raw_key: str) -> bool:
    """Verify a dynamic user API key against the default APIKeyManager and ALLOWED_USERS."""
    return verify_user_api_key_owner(raw_key) is not None
