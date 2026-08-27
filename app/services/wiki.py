"""David888 Wiki publisher and reader service client."""

import os
import re
import uuid
import datetime
import requests
from typing import Optional, Dict, Any

WIKI_API_BASE_URL = os.environ.get("WIKI_API_BASE_URL", "https://wiki.david888.com").rstrip("/")
DEFAULT_WIKI_THEME = os.environ.get("DEFAULT_WIKI_THEME", "tokyo-night")


def generate_wiki_slug(title: str = "") -> str:
    """Generate a clean path slug for David888 Wiki."""
    today = datetime.datetime.now().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6]
    if title:
        # Keep alphanumeric, Chinese chars, and hyphens
        clean_title = re.sub(r"[^\w一-鿿-]+", "-", title.strip())[:30].strip("-")
        if clean_title:
            return f"{clean_title}-{today}-{short_id}"
    return f"summary-{today}-{short_id}"


def publish_wiki_page(
    content: str,
    title: str = "",
    path: Optional[str] = None,
    theme: str = "",
    public: bool = True,
    timeout: int = 30
) -> Dict[str, Any]:
    """Publish or overwrite a Markdown page to David888 Wiki."""
    slug = path or generate_wiki_slug(title)
    url = f"{WIKI_API_BASE_URL}/api/{slug}"
    applied_theme = theme or DEFAULT_WIKI_THEME

    # Ensure title is header if content doesn't start with '#'
    formatted_content = content.strip()
    if title and not formatted_content.startswith("#"):
        formatted_content = f"# {title}\n\n{formatted_content}"

    payload = {
        "text": formatted_content,
        "public": public,
        "theme": applied_theme
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("err") == 0:
            res_data = data.get("data", {})
            share_url = res_data.get("shareUrl", "")
            return {
                "success": True,
                "path": slug,
                "shareUrl": share_url,
                "url": res_data.get("url", ""),
                "presentUrl": f"{share_url}/present" if share_url else ""
            }
        else:
            return {
                "success": False,
                "error": data.get("msg", "Wiki publish failed")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def append_wiki_page(
    path: str,
    content: str,
    timeout: int = 30
) -> Dict[str, Any]:
    """Append Markdown content to an existing David888 Wiki page."""
    url = f"{WIKI_API_BASE_URL}/api/{path}"
    payload = {
        "text": f"\n\n{content.strip()}",
        "append": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("err") == 0:
            res_data = data.get("data", {})
            share_url = res_data.get("shareUrl", "")
            return {
                "success": True,
                "path": path,
                "shareUrl": share_url,
                "url": res_data.get("url", ""),
            }
        else:
            return {
                "success": False,
                "error": data.get("msg", "Wiki append failed")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_wiki_page(
    path: str,
    timeout: int = 15
) -> Dict[str, Any]:
    """Read raw Markdown content from David888 Wiki."""
    url = f"{WIKI_API_BASE_URL}/api/{path}"
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            return {
                "success": True,
                "content": resp.text,
                "path": path
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
