"""David888 Wiki publisher and reader service client.

Follows the canonical specification from:
https://wiki.david888.com/.well-known/agent-skills/david888-wiki-publisher/SKILL.md
"""

import datetime
import os
import re
import urllib.parse
import uuid
from typing import Any, Dict, Optional
import requests

SUPPORTED_WIKI_THEMES = [
    "ayu-light", "bauhaus", "botanical", "catppuccin-latte", "catppuccin-macchiato",
    "claude-canvas", "green-simple", "kanagawa", "neo-brutalism", "newsprint",
    "notion-clean", "organic", "playful-geometric", "professional", "retro",
    "shopify-mint", "sketch", "terminal", "tokyo-night", "x-ai",
]


def _get_wiki_base_url() -> str:
    return os.environ.get("WIKI_API_BASE_URL", "https://wiki.david888.com").strip().rstrip("/")


def _get_default_wiki_theme() -> str:
    return os.environ.get("DEFAULT_WIKI_THEME", "tokyo-night").strip() or "tokyo-night"


def _validate_wiki_path(path: str) -> str:
    """Validate and normalize a Wiki page path to prevent traversal and query/fragment injection."""
    if not path or not isinstance(path, str):
        raise ValueError("Wiki path must not be empty.")
    clean = path.strip().lstrip("/")
    if not clean:
        raise ValueError("Wiki path must not be empty.")
    if any(ch in clean for ch in ("?", "#", "\\")) or any(ch.isspace() or ord(ch) < 32 for ch in clean):
        raise ValueError("Invalid characters in Wiki path.")
    segments = [seg for seg in clean.split("/") if seg]
    if not segments or any(seg in (".", "..") for seg in segments):
        raise ValueError("Path traversal segments are not allowed in Wiki path.")
    return "/".join(segments)


def _safe_json(resp: requests.Response) -> dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def generate_wiki_slug(title: str = "") -> str:
    """Generate a clean path slug for David888 Wiki."""
    today = datetime.datetime.now().strftime("%Y%m%d")
    short_id = uuid.uuid4().hex[:6]
    if title:
        clean_title = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title.strip())[:30].strip("-")
        if clean_title:
            return f"{clean_title}-{today}-{short_id}"
    return f"summary-{today}-{short_id}"


def sanitize_wiki_markdown(content: str, title: str = "") -> str:
    """Ensure markdown starts with `# Title` on the very first line (stripping leading YAML frontmatter/preamble)."""
    raw = (content or "").strip()

    # Strip leading YAML frontmatter block cleanly (match only at start, avoid splitting on horizontal rules `---`)
    fm_match = re.match(r"\A---\r?\n.*?\r?\n---(?:\r?\n|\Z)", raw, re.DOTALL)
    if fm_match:
        raw = raw[fm_match.end():].strip()

    # Locate first level-1 `# Title` outside fenced code blocks
    in_fence = False
    first_h1_idx: int | None = None
    offset = 0
    for line in raw.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        elif not in_fence and re.match(r"^#\s+\S", line):
            first_h1_idx = offset
            break
        offset += len(line)

    if first_h1_idx is not None:
        if first_h1_idx > 0:
            raw = raw[first_h1_idx:].strip()
    else:
        clean_t = title.strip() or "AI 深度分析報告"
        raw = f"# {clean_t}\n\n{raw}" if raw else f"# {clean_t}"

    return raw


def publish_wiki_page(
    content: str,
    title: str = "",
    path: Optional[str] = None,
    theme: str = "",
    public: bool = True,
    width: str = "100%",
    timeout: int = 30,
) -> Dict[str, Any]:
    """Publish or overwrite a Markdown page to David888 Wiki."""
    base_url = _get_wiki_base_url()
    default_theme = _get_default_wiki_theme()
    try:
        slug = _validate_wiki_path(path) if path else generate_wiki_slug(title)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    applied_theme = theme if theme in SUPPORTED_WIKI_THEMES else default_theme
    formatted_content = sanitize_wiki_markdown(content, title=title)
    encoded_slug = urllib.parse.quote(slug, safe="/-_.~")

    url = (
        f"{base_url}/api/{encoded_slug}"
        f"?public={str(public).lower()}&theme={urllib.parse.quote(applied_theme)}&width={urllib.parse.quote(width)}"
    )
    headers = {
        "Content-Type": "text/markdown; charset=UTF-8",
        "Accept": "application/json",
    }

    try:
        resp = requests.post(
            url,
            data=formatted_content.encode("utf-8"),
            headers=headers,
            timeout=timeout,
        )
        data = _safe_json(resp)
        res_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}

        if resp.status_code in (200, 201) and data and data.get("err", 0) == 0:
            share_url = res_data.get("shareUrl", "") or (
                f"{base_url}/share/{res_data['shareId']}" if res_data.get("shareId") else ""
            )
            page_url = res_data.get("url", "")
            if share_url or page_url:
                return {
                    "success": True,
                    "path": slug,
                    "shareUrl": share_url,
                    "url": page_url or f"{base_url}/{encoded_slug}",
                    "presentUrl": f"{share_url}/present" if share_url else "",
                    "bookUrl": f"{share_url}/book" if share_url else "",
                    "theme": applied_theme,
                }

        fallback_url = f"{base_url}/api/{encoded_slug}"
        payload = {
            "text": formatted_content,
            "public": public,
            "theme": applied_theme,
            "width": width,
        }
        f_resp = requests.post(fallback_url, json=payload, timeout=timeout)
        f_data = _safe_json(f_resp)
        f_res_data = f_data.get("data", {}) if isinstance(f_data.get("data"), dict) else {}
        if f_resp.status_code in (200, 201) and f_data and f_data.get("err", 0) == 0:
            share_url = f_res_data.get("shareUrl", "") or (
                f"{base_url}/share/{f_res_data['shareId']}" if f_res_data.get("shareId") else ""
            )
            page_url = f_res_data.get("url", "")
            if share_url or page_url:
                return {
                    "success": True,
                    "path": slug,
                    "shareUrl": share_url,
                    "url": page_url,
                    "presentUrl": f"{share_url}/present" if share_url else "",
                    "bookUrl": f"{share_url}/book" if share_url else "",
                    "theme": applied_theme,
                }
        return {
            "success": False,
            "error": data.get("msg") or f_data.get("msg") or f"HTTP {f_resp.status_code}: Wiki publish failed",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def append_wiki_page(
    path: str,
    content: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Append Markdown content to an existing David888 Wiki page."""
    base_url = _get_wiki_base_url()
    try:
        safe_path = _validate_wiki_path(path)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    encoded_path = urllib.parse.quote(safe_path, safe="/-_.~")
    url = f"{base_url}/api/{encoded_path}?append=true"
    headers = {
        "Content-Type": "text/markdown; charset=UTF-8",
        "Accept": "application/json",
    }

    try:
        resp = requests.post(
            url,
            data=f"\n\n{content.strip()}".encode("utf-8"),
            headers=headers,
            timeout=timeout,
        )
        data = _safe_json(resp)
        res_data = data.get("data", {}) if isinstance(data.get("data"), dict) else {}

        if resp.status_code in (200, 201) and data and data.get("err", 0) == 0:
            share_url = res_data.get("shareUrl", "") or (
                f"{base_url}/share/{res_data['shareId']}" if res_data.get("shareId") else ""
            )
            page_url = res_data.get("url", "")
            if share_url or page_url:
                return {
                    "success": True,
                    "path": safe_path,
                    "shareUrl": share_url,
                    "url": page_url,
                    "presentUrl": f"{share_url}/present" if share_url else "",
                    "bookUrl": f"{share_url}/book" if share_url else "",
                }

        fallback_url = f"{base_url}/api/{encoded_path}"
        payload = {
            "text": f"\n\n{content.strip()}",
            "append": True,
        }
        f_resp = requests.post(fallback_url, json=payload, timeout=timeout)
        f_data = _safe_json(f_resp)
        f_res_data = f_data.get("data", {}) if isinstance(f_data.get("data"), dict) else {}
        if f_resp.status_code in (200, 201) and f_data and f_data.get("err", 0) == 0:
            share_url = f_res_data.get("shareUrl", "") or (
                f"{base_url}/share/{f_res_data['shareId']}" if f_res_data.get("shareId") else ""
            )
            page_url = f_res_data.get("url", "")
            if share_url or page_url:
                return {
                    "success": True,
                    "path": safe_path,
                    "shareUrl": share_url,
                    "url": page_url,
                    "presentUrl": f"{share_url}/present" if share_url else "",
                    "bookUrl": f"{share_url}/book" if share_url else "",
                }
        return {
            "success": False,
            "error": data.get("msg") or f_data.get("msg") or f"HTTP {f_resp.status_code}: Wiki append failed",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def read_wiki_page(
    path: str,
    password: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Read raw Markdown content from David888 Wiki using content negotiation."""
    base_url = _get_wiki_base_url()
    try:
        clean_path = _validate_wiki_path(path)
    except ValueError as exc:
        return {"success": False, "error": str(exc)}

    if clean_path.startswith("share/"):
        url = f"{base_url}/{clean_path}"
    else:
        url = f"{base_url}/api/{clean_path}"

    headers = {"Accept": "text/markdown"}
    if password:
        headers["Authorization"] = f"Bearer {password}"

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return {
                "success": True,
                "content": resp.text,
                "path": clean_path,
            }
        if resp.status_code in (401, 403):
            return {
                "success": False,
                "error": "🔒 此頁面受密碼保護，請提供檢視密碼。",
            }
        return {
            "success": False,
            "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def render_markdown(
    markdown_text: str,
    theme: str = "tokyo-night",
    full_html: bool = False,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Render Markdown to HTML using David888 Wiki stateless API (/api/markdown/render)."""
    base_url = _get_wiki_base_url()
    default_theme = _get_default_wiki_theme()
    url = f"{base_url}/api/markdown/render"
    payload = {
        "markdown": markdown_text,
        "theme": theme if theme in SUPPORTED_WIKI_THEMES else default_theme,
        "fullHtml": full_html,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = _safe_json(resp)
        if data.get("err") == 0 and data:
            return {"success": True, "html": data.get("data", {}).get("html", "")}
        return {"success": False, "error": data.get("msg") or f"HTTP {resp.status_code}: Render failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def parse_web_to_markdown(
    url_or_html: str,
    is_url: bool = True,
    timeout: int = 20,
) -> Dict[str, Any]:
    """Parse Webpage or raw HTML to Markdown via /api/markdown/parse."""
    base_url = _get_wiki_base_url()
    url = f"{base_url}/api/markdown/parse"
    payload = {"url": url_or_html} if is_url else {"html": url_or_html}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = _safe_json(resp)
        if data.get("err") == 0 and data:
            return {"success": True, "markdown": data.get("data", {}).get("markdown", "")}
        return {"success": False, "error": data.get("msg") or f"HTTP {resp.status_code}: Parse failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def lint_markdown(
    markdown_text: str,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Lint and auto-fix Markdown via /api/markdown/lint."""
    base_url = _get_wiki_base_url()
    url = f"{base_url}/api/markdown/lint"
    payload = {"markdown": markdown_text}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        data = _safe_json(resp)
        if data.get("err") == 0 and data:
            res = data.get("data", {})
            return {
                "success": True,
                "valid": res.get("valid", True),
                "issues": res.get("issues", []),
                "fixedMarkdown": res.get("fixedMarkdown", markdown_text),
            }
        return {"success": False, "error": data.get("msg") or f"HTTP {resp.status_code}: Lint failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}
