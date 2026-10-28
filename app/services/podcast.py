"""Podcast extraction, resolution, and metadata services."""

import logging
import re
import urllib.parse
from functools import lru_cache
import requests

try:
    from app.services.content import is_safe_url
except ImportError:
    from services.content import is_safe_url

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


def resolve_pocketcasts_url(url: str, timeout: int = 10) -> str:
    """Resolve pca.st shortlinks or redirect URLs to canonical Pocket Casts URL."""
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
                    return resp.headers["Location"]
            except Exception:
                pass

            # Fallback to GET stream if HEAD fails or raises exception
            try:
                resp = requests.get(
                    current_url,
                    headers=BROWSER_HEADERS,
                    allow_redirects=False,
                    stream=True,
                    timeout=timeout,
                )
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("Location"):
                    return resp.headers["Location"]
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error resolving Pocket Casts shortlink {url}: {e}")
    return current_url


@lru_cache(maxsize=128)
def extract_pocketcasts_episode(url: str, timeout: int = 20) -> dict | None:
    """Extract episode information from a Pocket Casts URL (including pca.st and full pocketcasts.com URLs).

    Returns a dict with:
        podcast_title: str
        episode_title: str
        audio_url: str
        duration: int (seconds)
        published: str
        podcast_uuid: str
        episode_uuid: str
    or None if extraction fails.
    """
    if not url or not is_safe_url(url):
        return None

    canonical_url = resolve_pocketcasts_url(url, timeout=timeout)
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

                if not selected_ep and episodes:
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

    # Fallback: HTML scraping with modern browser headers
    try:
        resp = requests.get(canonical_url, headers=BROWSER_HEADERS, timeout=timeout)
        if resp.status_code == 200:
            html = resp.text
            # Look for direct audio URLs embedded in page/loader
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
