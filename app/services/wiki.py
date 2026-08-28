"""David888 Wiki publisher and reader service client.

Follows the canonical specification from:
https://wiki.david888.com/.well-known/agent-skills/david888-wiki-publisher/SKILL.md
"""

import os
import re
import uuid
import datetime
import requests
from typing import Optional, Dict, Any, List

WIKI_API_BASE_URL = os.environ.get("WIKI_API_BASE_URL", "https://wiki.david888.com").rstrip("/")
DEFAULT_WIKI_THEME = os.environ.get("DEFAULT_WIKI_THEME", "tokyo-night")

SUPPORTED_WIKI_THEMES = [
    "ayu-light", "bauhaus", "botanical", "catppuccin-latte", "catppuccin-macchiato",
    "claude-canvas", "green-simple", "kanagawa", "neo-brutalism", "newsprint",
    "notion-clean", "organic", "playful-geometric", "professional", "retro",
    "shopify-mint", "sketch", "terminal", "tokyo-night", "x-ai"
]


def generate_wiki_slug(title: str = "") -> str:
    """Generate a clean path slug for David888 Wiki."""
    today = datetime.datetime.now().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6]
    if title:
        # Keep alphanumeric, Chinese chars, and hyphens
        clean_title = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title.strip())[:30].strip("-")
        if clean_title:
            return f"{clean_title}-{today}-{short_id}"
    return f"summary-{today}-{short_id}"


def sanitize_wiki_markdown(content: str, title: str = "") -> str:
    """
    Ensure markdown adheres to the mandatory David888 Wiki structure:
    1. ALWAYS start with `# Title` on the very first line (or YAML frontmatter).
    2. Strip conversational preamble/chatter before the first heading.
    3. Ensure [TOC] and blockquotes are placed after `# Title`.
    """
    raw = content.strip()

    # If starts with YAML frontmatter, preserve it
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            fm = f"---{parts[1]}---"
            body = parts[2].strip()
            # Clean body to ensure it starts with # Heading
            if not body.startswith("#"):
                clean_t = title or "Document"
                body = f"# {clean_t}\n\n{body}"
            return f"{fm}\n\n{body}"

    # Remove conversational filler before the first level-1 or level-2 heading if present
    match = re.search(r"(?m)^#\s+(.+)$", raw)
    if match:
        start_idx = match.start()
        # If there is introductory preamble text before `# `, strip it
        if start_idx > 0:
            raw = raw[start_idx:].strip()
    else:
        # No level-1 heading found, prepend title
        clean_t = title.strip() or "AI 深度分析報告"
        raw = f"# {clean_t}\n\n{raw}"

    return raw


def publish_wiki_page(
    content: str,
    title: str = "",
    path: Optional[str] = None,
    theme: str = "",
    public: bool = True,
    width: str = "100%",
    timeout: int = 30
) -> Dict[str, Any]:
    """
    Publish or overwrite a Markdown page to David888 Wiki.
    Guarantees raw markdown starts with `# Title` and returns shareUrl, presentUrl, bookUrl.
    """
    slug = path or generate_wiki_slug(title)
    applied_theme = theme if theme in SUPPORTED_WIKI_THEMES else DEFAULT_WIKI_THEME
    formatted_content = sanitize_wiki_markdown(content, title=title)

    # Use direct raw markdown POST with query params as recommended in spec
    url = f"{WIKI_API_BASE_URL}/api/{slug}?public={str(public).lower()}&theme={applied_theme}&width={width}"
    headers = {
        "Content-Type": "text/markdown; charset=UTF-8",
        "Accept": "application/json"
    }

    try:
        resp = requests.post(
            url,
            data=formatted_content.encode("utf-8"),
            headers=headers,
            timeout=timeout
        )
        # If server returns json
        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code in [200, 201] and data.get("err", 0) == 0:
            res_data = data.get("data", {})
            share_url = res_data.get("shareUrl", "")
            if not share_url and res_data.get("shareId"):
                share_url = f"{WIKI_API_BASE_URL}/share/{res_data['shareId']}"
            elif not share_url and "share" in str(data):
                share_url = f"{WIKI_API_BASE_URL}/share/{slug}"

            return {
                "success": True,
                "path": slug,
                "shareUrl": share_url,
                "url": res_data.get("url", f"{WIKI_API_BASE_URL}/{slug}"),
                "presentUrl": f"{share_url}/present" if share_url else "",
                "bookUrl": f"{share_url}/book" if share_url else "",
                "theme": applied_theme,
            }
        else:
            # Fallback to JSON payload if binary was rejected
            fallback_url = f"{WIKI_API_BASE_URL}/api/{slug}"
            payload = {
                "text": formatted_content,
                "public": public,
                "theme": applied_theme
            }
            f_resp = requests.post(fallback_url, json=payload, timeout=timeout)
            f_data = f_resp.json()
            if f_data.get("err") == 0:
                res_data = f_data.get("data", {})
                share_url = res_data.get("shareUrl", "")
                return {
                    "success": True,
                    "path": slug,
                    "shareUrl": share_url,
                    "url": res_data.get("url", ""),
                    "presentUrl": f"{share_url}/present" if share_url else "",
                    "bookUrl": f"{share_url}/book" if share_url else "",
                    "theme": applied_theme,
                }
            return {
                "success": False,
                "error": data.get("msg") or f_data.get("msg", "Wiki publish failed")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def append_wiki_page(
    path: str,
    content: str,
    timeout: int = 30
) -> Dict[str, Any]:
    """Append Markdown content to an existing David888 Wiki page."""
    url = f"{WIKI_API_BASE_URL}/api/{path}?append=true"
    headers = {
        "Content-Type": "text/markdown; charset=UTF-8",
        "Accept": "application/json"
    }

    try:
        resp = requests.post(
            url,
            data=f"\n\n{content.strip()}".encode("utf-8"),
            headers=headers,
            timeout=timeout
        )
        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code in [200, 201] and data.get("err", 0) == 0:
            res_data = data.get("data", {})
            share_url = res_data.get("shareUrl", "")
            return {
                "success": True,
                "path": path,
                "shareUrl": share_url,
                "url": res_data.get("url", ""),
                "presentUrl": f"{share_url}/present" if share_url else "",
                "bookUrl": f"{share_url}/book" if share_url else "",
            }
        else:
            # Fallback to JSON payload
            fallback_url = f"{WIKI_API_BASE_URL}/api/{path}"
            payload = {
                "text": f"\n\n{content.strip()}",
                "append": True
            }
            f_resp = requests.post(fallback_url, json=payload, timeout=timeout)
            f_data = f_resp.json()
            if f_data.get("err") == 0:
                res_data = f_data.get("data", {})
                share_url = res_data.get("shareUrl", "")
                return {
                    "success": True,
                    "path": path,
                    "shareUrl": share_url,
                    "url": res_data.get("url", ""),
                    "presentUrl": f"{share_url}/present" if share_url else "",
                    "bookUrl": f"{share_url}/book" if share_url else "",
                }
            return {
                "success": False,
                "error": data.get("msg") or f_data.get("msg", "Wiki append failed")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_wiki_page(
    path: str,
    password: Optional[str] = None,
    timeout: int = 15
) -> Dict[str, Any]:
    """
    Read raw Markdown content from David888 Wiki.
    Uses Accept: text/markdown header for content negotiation.
    """
    clean_path = path.strip().lstrip("/")
    if clean_path.startswith("share/"):
        url = f"{WIKI_API_BASE_URL}/{clean_path}"
    else:
        url = f"{WIKI_API_BASE_URL}/api/{clean_path}"

    headers = {"Accept": "text/markdown"}
    if password:
        headers["Authorization"] = f"Bearer {password}"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return {
                "success": True,
                "content": resp.text,
                "path": clean_path
            }
        elif resp.status_code in [401, 403]:
            return {
                "success": False,
                "error": "🔒 此頁面受密碼保護，請提供檢視密碼。"
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text}"
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def render_markdown(
    markdown_text: str,
    theme: str = "tokyo-night",
    full_html: bool = False,
    timeout: int = 15
) -> Dict[str, Any]:
    """Render Markdown to HTML using David888 Wiki stateless API (/api/markdown/render)."""
    url = f"{WIKI_API_BASE_URL}/api/markdown/render"
    payload = {
        "markdown": markdown_text,
        "theme": theme if theme in SUPPORTED_WIKI_THEMES else DEFAULT_WIKI_THEME,
        "fullHtml": full_html
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("err") == 0:
            return {"success": True, "html": data.get("data", {}).get("html", "")}
        return {"success": False, "error": data.get("msg", "Render failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_web_to_markdown(
    url_or_html: str,
    is_url: bool = True,
    timeout: int = 20
) -> Dict[str, Any]:
    """Parse Webpage or raw HTML to Markdown via /api/markdown/parse."""
    url = f"{WIKI_API_BASE_URL}/api/markdown/parse"
    payload = {"url": url_or_html} if is_url else {"html": url_or_html}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("err") == 0:
            return {"success": True, "markdown": data.get("data", {}).get("markdown", "")}
        return {"success": False, "error": data.get("msg", "Parse failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lint_markdown(
    markdown_text: str,
    timeout: int = 15
) -> Dict[str, Any]:
    """Lint and auto-fix Markdown via /api/markdown/lint."""
    url = f"{WIKI_API_BASE_URL}/api/markdown/lint"
    payload = {"markdown": markdown_text}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = resp.json()
        if data.get("err") == 0:
            res = data.get("data", {})
            return {
                "success": True,
                "valid": res.get("valid", True),
                "issues": res.get("issues", []),
                "fixedMarkdown": res.get("fixedMarkdown", markdown_text)
            }
        return {"success": False, "error": data.get("msg", "Lint failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}
