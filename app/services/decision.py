"""Clef-Flash Decision API Service for Content Classification and Ad Detection (System One)."""

import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from typing import Any, Optional, Tuple, Union
import requests

logger = logging.getLogger(__name__)

PRIMARY_CLEF_URL = os.environ.get(
    "CLEF_PRIMARY_URL", "https://clef.create360.ai/v1/systemone"
)
FALLBACK_CLEF_URL = os.environ.get(
    "CLEF_FALLBACK_URL", "https://clef.aiurl.tw/v1/systemone"
)
CLEF_TIMEOUT_SECONDS = float(os.environ.get("CLEF_TIMEOUT_SECONDS", "30.0"))

# In-memory cache
_CACHE_LOCK = threading.Lock()
_MEMORY_CACHE: dict[str, dict[str, Any]] = {}
_MAX_MEMORY_CACHE_SIZE = 10000

# Local disk cache fallback
LOCAL_CACHE_DIR = ".cache"
LOCAL_CACHE_FILE = os.path.join(LOCAL_CACHE_DIR, "ad_decisions.json")


def is_decision_ad_filter_enabled(user_pref: Optional[bool] = None) -> bool:
    """Check if ad filtering is enabled, with user preference taking priority over default."""
    if user_pref is not None:
        return bool(user_pref)
    val = os.environ.get("DECISION_AD_FILTER_ENABLED", "true").strip().lower()
    return val in ("true", "1", "yes", "on")


def _load_local_disk_cache_unlocked() -> dict[str, dict[str, Any]]:
    try:
        if os.path.exists(LOCAL_CACHE_FILE):
            with open(LOCAL_CACHE_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                return loaded if isinstance(loaded, dict) else {}
    except Exception as e:
        logger.debug(f"Failed to read local decision cache: {e}")
    return {}


def _load_local_disk_cache() -> dict[str, dict[str, Any]]:
    with _CACHE_LOCK:
        return _load_local_disk_cache_unlocked()


def _save_local_disk_cache(data: dict[str, Any]):
    with _CACHE_LOCK:
        tmp_path: Optional[str] = None
        try:
            os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)
            existing = _load_local_disk_cache_unlocked()
            existing.update(data)
            if len(existing) > 5000:
                keys = list(existing.keys())[-5000:]
                existing = {k: existing[k] for k in keys}
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=LOCAL_CACHE_DIR,
                prefix=".ad_decisions_",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                tmp_path = tmp_file.name
                json.dump(existing, tmp_file, ensure_ascii=False)
                tmp_file.flush()
            os.replace(tmp_path, LOCAL_CACHE_FILE)
        except Exception as e:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            logger.debug(f"Failed to save local decision cache: {e}")


_DECISION_CACHE_TTL_SECONDS = 86400  # 24h expiry for ad decision cache entries


def _is_entry_expired(entry: Any, ts_hint: Any = None) -> bool:
    raw_ts = None
    if isinstance(entry, dict) and entry.get("_cached_at") is not None:
        raw_ts = entry.get("_cached_at")
    elif ts_hint is not None:
        raw_ts = ts_hint
    if raw_ts is None:
        return False
    try:
        return (time.time() - float(raw_ts)) > _DECISION_CACHE_TTL_SECONDS
    except Exception:
        return False


def get_cached_decision(
    cache_keys: list[str], mongo_collection: Any = None
) -> Optional[dict[str, Any]]:
    """Look up cached decision result from Memory -> MongoDB -> Disk file."""
    with _CACHE_LOCK:
        for k in cache_keys:
            if k in _MEMORY_CACHE:
                entry = _MEMORY_CACHE[k]
                if not _is_entry_expired(entry):
                    return entry
                _MEMORY_CACHE.pop(k, None)

    if mongo_collection is not None:
        try:
            for k in cache_keys:
                doc = mongo_collection.find_one({"_id": k})
                if doc and "decision" in doc:
                    dec = doc["decision"]
                    if _is_entry_expired(dec, doc.get("timestamp")):
                        continue
                    with _CACHE_LOCK:
                        _MEMORY_CACHE[k] = dec
                    return dec
        except Exception as e:
            logger.debug(f"MongoDB decision cache lookup failed: {e}")
        return None

    disk_cache = _load_local_disk_cache()
    for k in cache_keys:
        if k in disk_cache:
            dec = disk_cache[k]
            if _is_entry_expired(dec):
                continue
            with _CACHE_LOCK:
                _MEMORY_CACHE[k] = dec
            return dec

    return None


def store_cached_decision(
    cache_keys: list[str], decision: dict[str, Any], mongo_collection: Any = None
):
    """Store decision result into Memory and MongoDB (or Disk fallback when MongoDB is absent)."""
    dec_to_store = dict(decision)
    dec_to_store.setdefault("_cached_at", time.time())
    with _CACHE_LOCK:
        if len(_MEMORY_CACHE) >= _MAX_MEMORY_CACHE_SIZE:
            keys_to_drop = list(_MEMORY_CACHE.keys())[:1000]
            for k in keys_to_drop:
                _MEMORY_CACHE.pop(k, None)
        for k in cache_keys:
            _MEMORY_CACHE[k] = dec_to_store

    if mongo_collection is not None:
        try:
            for k in cache_keys:
                mongo_collection.update_one(
                    {"_id": k},
                    {"$set": {"_id": k, "decision": dec_to_store, "timestamp": time.time()}},
                    upsert=True,
                )
        except Exception as e:
            logger.debug(f"MongoDB decision cache save failed: {e}")
        return

    _save_local_disk_cache({k: dec_to_store for k in cache_keys})


def clear_decision_cache(clear_disk: bool = True):
    """Clear memory and disk cache (useful for testing)."""
    with _CACHE_LOCK:
        _MEMORY_CACHE.clear()
        if clear_disk and os.path.exists(LOCAL_CACHE_FILE):
            try:
                os.remove(LOCAL_CACHE_FILE)
            except Exception:
                pass


def call_clef_systemone(
    text: str, timeout: float | None = None
) -> dict[str, Any]:
    """Call Clef System One API with automatic Primary -> Fallback failover."""
    effective_timeout = float(os.environ.get("CLEF_TIMEOUT_SECONDS", str(CLEF_TIMEOUT_SECONDS))) if timeout is None else timeout
    primary_url = os.environ.get("CLEF_PRIMARY_URL", PRIMARY_CLEF_URL)
    fallback_url = os.environ.get("CLEF_FALLBACK_URL", FALLBACK_CLEF_URL)

    truncated_text = text[:3000].strip()
    payload = {
        "state": {"text": truncated_text},
        "questions": {
            "classification": {
                "type": "choice",
                "instructions": (
                    "What is the primary nature of this content? Is it an advertisement, "
                    "commercial promotion, spam, or normal informative content?"
                ),
                "criteria": {
                    "ad": (
                        "Commercial advertisement, marketing promotion, spam, promotional sales pitch, "
                        "influencer endorsement, or financial investment / stock lure."
                    ),
                    "normal": (
                        "Normal article, news report, tutorial, educational content, transcript, "
                        "personal blog post, discussion, or genuine non-promotional information."
                    ),
                },
            }
        },
    }

    endpoints = [
        ("Primary (Clef-Flash)", primary_url),
        ("Fallback (Clef-Flash-Q4)", fallback_url),
    ]

    last_error = None
    for name, endpoint in endpoints:
        if not endpoint:
            continue
        try:
            logger.info(f"[Clef] Evaluating decision on {name} ({endpoint})...")
            start_t = time.time()
            resp = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=effective_timeout,
            )
            elapsed = time.time() - start_t
            if resp.status_code == 200:
                data = resp.json()
                answers = data.get("answers") if isinstance(data, dict) else None
                classification = answers.get("classification") if isinstance(answers, dict) else None
                if not isinstance(classification, dict) or not isinstance(classification.get("choice"), str):
                    logger.warning("[Clef INVALID] %s returned incomplete classification payload", name)
                    last_error = "Invalid classification schema"
                    continue
                choice = classification["choice"]
                confidence = float(classification.get("confidence", 0.0))
                probabilities = classification.get("probabilities") if isinstance(classification.get("probabilities"), dict) else {}
                prob_ad = float(probabilities.get("ad", 0.0))

                is_ad = (choice == "ad") and (prob_ad >= 0.70)

                logger.info(
                    f"[Clef SUCCESS] {name} in {elapsed:.2f}s -> choice: {choice} (prob_ad: {prob_ad:.3f}, is_ad: {is_ad})"
                )
                return {
                    "success": True,
                    "is_ad": is_ad,
                    "choice": choice,
                    "confidence": confidence,
                    "prob_ad": prob_ad,
                    "probabilities": probabilities,
                    "endpoint_used": endpoint,
                    "model": data.get("model", ""),
                }
            logger.warning(
                f"[Clef FAIL] {name} returned HTTP {resp.status_code}: {resp.text[:200]}"
            )
            last_error = f"HTTP {resp.status_code}"
        except Exception as e:
            logger.warning(f"[Clef EXCEPTION] {name} failed: {e}")
            last_error = str(e)

    logger.warning(
        f"[Clef CRITICAL] Both primary and fallback decision endpoints failed. Last error: {last_error}. Gracefully proceeding as non-ad."
    )
    return {
        "success": False,
        "is_ad": False,
        "choice": "normal",
        "prob_ad": 0.0,
        "error": last_error,
        "fallback_triggered": True,
    }


def is_advertisement_content(
    content: Union[str, list[str]],
    url: Optional[str] = None,
    mongo_collection: Any = None,
    timeout: float | None = None,
) -> Tuple[bool, dict[str, Any]]:
    """Determine if content is an advertisement with multi-tier caching and failover."""
    if isinstance(content, list):
        full_text = "\n".join(str(item) for item in content if item).strip()
    else:
        full_text = str(content or "").strip()

    if len(full_text) < 20 and not url:
        return False, {"reason": "too_short", "is_ad": False}

    # Lookup uses exact content hash when text is available so updated URLs re-evaluate;
    # fall back to URL key only when classifying without extracted text.
    store_keys = []
    if full_text:
        content_hash = hashlib.sha256(full_text[:4000].encode("utf-8")).hexdigest()
        store_keys.append(f"hash:{content_hash}")

    if url and isinstance(url, str):
        url_clean = url.strip()
        if mongo_collection is not None:
            from app.services.api_keys import get_bot_scope

            url_key = f"url:{get_bot_scope()}:{url_clean}"
        else:
            url_key = f"url:{url_clean}"
        store_keys.append(url_key)

    lookup_keys = [store_keys[0]] if full_text else list(store_keys)

    cached = get_cached_decision(lookup_keys, mongo_collection=mongo_collection)
    if cached is not None:
        logger.info(
            f"[Clef Cache HIT] Decision hit cache for {lookup_keys[0]} -> is_ad={cached.get('is_ad')}"
        )
        decision_copy = dict(cached)
        decision_copy["cached"] = True
        return bool(cached.get("is_ad", False)), decision_copy

    eval_text = full_text if full_text else (url or "")
    res = call_clef_systemone(eval_text, timeout=timeout)

    cache_id = hashlib.md5(eval_text[:1000].encode("utf-8")).hexdigest()[:12]
    res["cache_id"] = cache_id

    if res.get("success"):
        store_cached_decision(store_keys, res, mongo_collection=mongo_collection)

    return bool(res.get("is_ad", False)), res
