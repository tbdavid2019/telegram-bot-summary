"""Podcast extraction, resolution, RSS parsing, and transcription services."""

import logging
import os
import re
import tempfile
import threading
import time
import urllib.parse
from bs4 import BeautifulSoup
import feedparser
import requests

try:
    from app.services.content import is_safe_url, safe_http_get, transcribe_local_audio
except ImportError:
    from services.content import is_safe_url, safe_http_get, transcribe_local_audio

logger = logging.getLogger(__name__)

UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

POCKETCASTS_API_HEADERS = {
    "User-Agent": "Pocket Casts",
    "Accept": "application/json",
}

_PODCAST_CACHE_TTL_SECONDS = 600.0
_PODCAST_CACHE_MAX_SIZE = 128
_podcast_cache_lock = threading.Lock()
_podcast_episode_cache: dict[tuple[str, int], tuple[float, dict | None]] = {}
_MAX_PODCAST_BYTES = 500 * 1024 * 1024


def is_pocketcasts_url(url: str) -> bool:
    """Check if the URL is a Pocket Casts URL (including pca.st shortlinks and pocketcasts.com)."""
    if not url or not isinstance(url, str):
        return False
    try:
        url_clean = url.strip()
        if not re.match(r"^https?://", url_clean, re.I):
            url_clean = f"https://{url_clean}"
        parsed = urllib.parse.urlparse(url_clean)
        host = (parsed.hostname or "").lower()
        return (
            host == "pca.st"
            or host.endswith(".pca.st")
            or host == "pocketcasts.com"
            or host.endswith(".pocketcasts.com")
        )
    except Exception:
        return False


def _hostname(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    candidate = url.strip()
    if "://" not in candidate and not candidate.startswith("//"):
        candidate = f"https://{candidate}"
    elif candidate.startswith("//"):
        candidate = f"https:{candidate}"
    try:
        return (urllib.parse.urlparse(candidate).hostname or "").lower()
    except Exception:
        return ""


def is_soundon_url(url: str) -> bool:
    """Check whether URL belongs to SoundOn."""
    host = _hostname(url)
    return host == "soundon.fm" or host.endswith(".soundon.fm")


def is_apple_podcast_url(url: str) -> bool:
    """Check whether URL belongs to Apple Podcasts."""
    host = _hostname(url)
    return host == "podcasts.apple.com" or host.endswith(".podcasts.apple.com")


def resolve_pocketcasts_url(url: str, timeout: int = 10) -> str:
    """Resolve pca.st shortlinks or redirect URLs to canonical Pocket Casts URL (SSRF-validated)."""
    if not url or not isinstance(url, str):
        return url
    if not is_safe_url(url):
        return url

    current_url = url.strip()
    try:
        parsed = urllib.parse.urlparse(current_url)
        host = (parsed.hostname or "").lower()
        if "pca.st" in host:
            try:
                resp = requests.head(
                    current_url,
                    headers={"User-Agent": "Pocket Casts"},
                    allow_redirects=False,
                    timeout=timeout,
                )
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                    candidate = urllib.parse.urljoin(current_url, resp.headers["Location"])
                    if is_safe_url(candidate):
                        return candidate
                    return current_url
            except Exception:
                pass

            try:
                resp = requests.get(
                    current_url,
                    headers=BROWSER_HEADERS,
                    allow_redirects=False,
                    stream=True,
                    timeout=timeout,
                )
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                    candidate = urllib.parse.urljoin(current_url, resp.headers["Location"])
                    if is_safe_url(candidate):
                        return candidate
                    return current_url
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error resolving Pocket Casts shortlink {url}: {e}")
    return current_url


def _extract_pocketcasts_episode_uncached(url: str, timeout: int = 20) -> dict | None:
    if not url or not is_safe_url(url):
        return None

    canonical_url = resolve_pocketcasts_url(url, timeout=timeout)
    if not is_safe_url(canonical_url):
        return None
    uuids = UUID_PATTERN.findall(canonical_url)

    if uuids:
        podcast_uuid = uuids[0]
        episode_uuid = uuids[1] if len(uuids) > 1 else None

        api_url = f"https://podcast-api.pocketcasts.com/podcast/full/{podcast_uuid}"
        try:
            resp = requests.get(api_url, headers=POCKETCASTS_API_HEADERS, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                podcast_data = data.get("podcast", {})
                podcast_title = podcast_data.get("title", "")
                episodes = podcast_data.get("episodes", [])

                selected_ep = None
                if episode_uuid:
                    for ep in episodes:
                        if ep.get("uuid", "").lower() == episode_uuid.lower():
                            selected_ep = ep
                            break
                    if not selected_ep:
                        return None
                elif episodes:
                    selected_ep = episodes[0]

                if selected_ep and selected_ep.get("url"):
                    return {
                        "podcast_title": podcast_title,
                        "episode_title": selected_ep.get("title", ""),
                        "audio_url": selected_ep.get("url", ""),
                        "duration": selected_ep.get("duration", 0),
                        "published": selected_ep.get("published", ""),
                        "podcast_uuid": podcast_uuid,
                        "episode_uuid": selected_ep.get("uuid", ""),
                    }
        except Exception as e:
            logger.warning(f"Pocket Casts API call failed for {podcast_uuid}: {e}")

    try:
        resp = safe_http_get(canonical_url, headers=BROWSER_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            html = resp.text
            media_match = re.search(
                r'https?://[^\s\"\'<>]+?\.(?:mp3|m4a|aac|ogg)[^\s\"\'<>]*',
                html,
                re.IGNORECASE,
            )
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ""
            if " - Pocket Casts" in title:
                title = title.replace(" - Pocket Casts", "").strip()

            if media_match:
                return {
                    "podcast_title": "",
                    "episode_title": title,
                    "audio_url": media_match.group(0),
                    "duration": 0,
                    "published": "",
                    "podcast_uuid": uuids[0] if uuids else "",
                    "episode_uuid": uuids[1] if len(uuids) > 1 else "",
                }
    except Exception as e:
        logger.warning(f"Pocket Casts HTML fallback scrape failed for {canonical_url}: {e}")

    return None


def extract_pocketcasts_episode(url: str, timeout: int = 20) -> dict | None:
    """Extract episode info from a Pocket Casts URL with a short TTL cache."""
    cache_key = (url, timeout)
    now = time.monotonic()
    with _podcast_cache_lock:
        entry = _podcast_episode_cache.get(cache_key)
        if entry is not None and (now - entry[0]) < _PODCAST_CACHE_TTL_SECONDS:
            return entry[1]

    result = _extract_pocketcasts_episode_uncached(url, timeout=timeout)
    with _podcast_cache_lock:
        if len(_podcast_episode_cache) >= _PODCAST_CACHE_MAX_SIZE:
            oldest_key = min(_podcast_episode_cache, key=lambda k: _podcast_episode_cache[k][0])
            _podcast_episode_cache.pop(oldest_key, None)
        _podcast_episode_cache[cache_key] = (now, result)
    return result


def _clear_podcast_cache() -> None:
    with _podcast_cache_lock:
        _podcast_episode_cache.clear()


extract_pocketcasts_episode.cache_clear = _clear_podcast_cache  # type: ignore[attr-defined]


def get_pocketcasts_title(url: str) -> str | None:
    """Get human-readable title for a Pocket Casts URL."""
    try:
        info = extract_pocketcasts_episode(url)
        if not info:
            return None
        ep_title = (info.get("episode_title") or "").strip()
        pod_title = (info.get("podcast_title") or "").strip()
        if ep_title and pod_title and pod_title not in ep_title:
            return f"{ep_title} - {pod_title}"
        return ep_title or pod_title or None
    except Exception:
        return None


def extract_rss_from_pocketcasts(url: str, timeout: int = 30) -> str | None:
    """Extract RSS feed URL from a Pocket Casts web page."""
    try:
        response = safe_http_get(url, headers=BROWSER_HEADERS, timeout=timeout)
        response.raise_for_status()
        patterns = [
            r'"feedUrl"\s*:\s*"([^"]+)"',
            r'"feed_url"\s*:\s*"([^"]+)"',
            r'"rssUrl"\s*:\s*"([^"]+)"',
            r'feed[Uu]rl["\']?\s*[:=]\s*["\']([^"\',]+)["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, response.text)
            if match:
                return match.group(1).replace("\\/", "/")
        return None
    except Exception as e:
        logger.warning(f"Error extracting RSS from Pocket Casts: {e}")
        return None


def extract_rss_from_soundon(url: str, timeout: int = 30) -> str | None:
    """Extract RSS feed URL from a SoundOn page."""
    try:
        response = safe_http_get(url, headers=BROWSER_HEADERS, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        rss_link = soup.find("link", {"type": "application/rss+xml"})
        if rss_link and rss_link.get("href"):
            return rss_link.get("href")

        meta_rss = soup.find("meta", {"property": "og:rss"})
        if meta_rss and meta_rss.get("content"):
            return meta_rss.get("content")

        patterns = [
            r'"rss"\s*:\s*"([^"]+)"',
            r'"feedUrl"\s*:\s*"([^"]+)"',
            r'https://[^"\s]+\.rss',
            r'https://feeds\.soundon\.fm/[^"\s]+',
        ]
        for pattern in patterns:
            match = re.search(pattern, response.text)
            if match:
                rss_url = match.group(0) if "https://" in pattern else match.group(1)
                return rss_url.replace("\\/", "/")
        return None
    except Exception as e:
        logger.warning(f"Error extracting RSS from SoundOn: {e}")
        return None


def extract_episode_from_apple_podcast(url: str, timeout: int = 30) -> dict | None:
    """Resolve an Apple Podcasts URL (including ?i=<episode_id>) via iTunes Lookup API."""
    try:
        if not is_safe_url(url):
            return None
        match = re.search(r"/id(\d+)", url)
        if not match:
            return None
        podcast_id = match.group(1)
        ep_match = re.search(r"[?&]i=(\d+)", url)
        target_ep_id = ep_match.group(1) if ep_match else None

        entity = "podcastEpisode" if target_ep_id else "podcast"
        limit_q = "&limit=200" if target_ep_id else ""
        api_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity={entity}{limit_q}"
        response = safe_http_get(api_url, headers=BROWSER_HEADERS, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", []) or []

        rss_url = None
        matched_episode = None
        for result in results:
            if result.get("kind") == "podcast" and result.get("feedUrl") and not rss_url:
                rss_url = result.get("feedUrl")
            if target_ep_id and result.get("kind") == "podcast-episode":
                if str(result.get("trackId", "")) == target_ep_id and result.get("episodeUrl"):
                    matched_episode = {
                        "title": result.get("trackName", "Apple Podcast Episode"),
                        "audio_url": result.get("episodeUrl"),
                        "description": result.get("description", ""),
                    }
                    break
        return {
            "rss_url": rss_url,
            "episode": matched_episode,
            "target_episode_id": target_ep_id,
        }
    except Exception as e:
        logger.warning(f"Error extracting episode/RSS from Apple Podcast: {e}")
        return None


def extract_rss_from_apple_podcast(url: str, timeout: int = 30) -> str | None:
    """Extract RSS feed URL from an Apple Podcast page via iTunes Lookup API."""
    info = extract_episode_from_apple_podcast(url, timeout=timeout)
    if not info:
        return None
    return info.get("rss_url")


def get_latest_podcast_episode(rss_url: str, max_episodes: int = 1, timeout: int = 30) -> list[dict]:
    """Fetch RSS XML safely and return latest podcast episode metadata."""
    try:
        resp = safe_http_get(rss_url, headers=BROWSER_HEADERS, timeout=timeout)
        resp.raise_for_status()
        base_url = getattr(resp, "url", None) or rss_url
        feed = feedparser.parse(resp.content)
        if not feed.entries:
            return []

        episodes = []
        for entry in feed.entries:
            title = entry.get("title", "Unknown Episode")
            audio_url = None
            if hasattr(entry, "enclosures") and entry.enclosures:
                for enclosure in entry.enclosures:
                    if "audio" in enclosure.get("type", ""):
                        audio_url = enclosure.get("href") or enclosure.get("url")
                        break
            if not audio_url and hasattr(entry, "links"):
                for link in entry.links:
                    if "audio" in link.get("type", ""):
                        audio_url = link.get("href")
                        break
            if not audio_url and hasattr(entry, "media_content"):
                for media in entry.media_content:
                    if "audio" in media.get("type", ""):
                        audio_url = media.get("url")
                        break
            if audio_url:
                resolved_audio = urllib.parse.urljoin(base_url, audio_url) if isinstance(base_url, str) else audio_url
                episodes.append({
                    "title": title,
                    "audio_url": resolved_audio,
                    "description": entry.get("summary", ""),
                })
                if len(episodes) >= max_episodes:
                    break
        return episodes
    except Exception as e:
        logger.warning(f"Error parsing RSS feed: {e}")
        return []


def split_transcript_lines(transcript: str, chunk_size: int = 2100) -> list[str]:
    """Split newline-delimited transcript into chunks <= chunk_size."""
    output_lines = [line.strip() for line in (transcript or "").split("\n") if line.strip()]
    output_chunks: list[str] = []
    current_chunk = ""
    for line in output_lines:
        if len(current_chunk) + len(line) + 1 <= chunk_size:
            current_chunk += line + "\n"
        else:
            if current_chunk.strip():
                output_chunks.append(current_chunk.strip())
            current_chunk = line + "\n"
    if current_chunk.strip():
        output_chunks.append(current_chunk.strip())
    return output_chunks


def download_and_transcribe_podcast(
    audio_url: str,
    chunk_size: int | None = None,
    download_timeout: float | None = None,
    asr_timeout: float | None = None,
) -> list[str]:
    """Safely download podcast audio into a temporary directory and transcribe via Whisper ASR."""
    if not is_safe_url(audio_url):
        return ["不支援或受保護的私有/內部網路網址。"]

    effective_chunk_size = int(os.environ.get("CHUNK_SIZE", "2100")) if chunk_size is None else chunk_size
    effective_dl_timeout = (
        float(os.environ.get("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "900"))
        if download_timeout is None
        else download_timeout
    )

    try:
        with tempfile.TemporaryDirectory(prefix="podcast_") as tmp_dir:
            temp_audio_path = os.path.join(tmp_dir, "episode.mp3")
            resp = safe_http_get(audio_url, headers=BROWSER_HEADERS, stream=True, timeout=effective_dl_timeout)
            try:
                resp.raise_for_status()
                content_len = resp.headers.get("Content-Length")
                if content_len and content_len.isdigit() and int(content_len) > _MAX_PODCAST_BYTES:
                    return ["Podcast 音頻轉錄失敗。"]

                total_bytes = 0
                with open(temp_audio_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            total_bytes += len(chunk)
                            if total_bytes > _MAX_PODCAST_BYTES:
                                return ["Podcast 音頻轉錄失敗。"]
                            f.write(chunk)
            finally:
                resp.close()

            transcript = transcribe_local_audio(temp_audio_path, asr_timeout=asr_timeout)
            return split_transcript_lines(transcript, chunk_size=effective_chunk_size)
    except Exception as e:
        logger.warning(f"Error downloading and transcribing podcast: {e}")
        return ["Podcast 音頻轉錄失敗。"]
