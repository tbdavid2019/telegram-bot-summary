"""Content classification and extraction helpers."""

import ipaddress
import re
import socket
import urllib.parse


def split_user_input(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]


def is_url(text: str) -> bool:
    return bool(re.compile(r"https?://\S+|www\.\S+").match(text))


def is_safe_url(url: str) -> bool:
    """Validate that a URL uses http/https and does not point to internal/private/loopback IPs or cloud metadata services (SSRF protection)."""
    if not url or not isinstance(url, str):
        return False
    try:
        url_clean = url.strip()
        # If a scheme is explicitly provided, it MUST be http or https
        if "://" in url_clean:
            scheme = url_clean.split("://", 1)[0].lower()
            if scheme not in ("http", "https"):
                return False
            url_to_parse = url_clean
        elif url_clean.startswith("//"):
            url_to_parse = f"http:{url_clean}"
        else:
            url_to_parse = f"http://{url_clean}"

        parsed = urllib.parse.urlparse(url_to_parse)
        if parsed.scheme.lower() not in ("http", "https"):
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        hostname_lower = hostname.lower()

        # Block loopback, localhost, and cloud metadata hostnames
        blocked_hostnames = {
            "localhost",
            "localhost.localdomain",
            "ip6-localhost",
            "ip6-loopback",
            "metadata.google.internal",
            "metadata.aws",
            "169.254.169.254",
            "0.0.0.0",
        }
        if hostname_lower in blocked_hostnames:
            return False

        if hostname_lower.endswith((".local", ".localhost", ".internal", ".lan", ".corp", ".localdomain")):
            return False

        # Direct IP check
        try:
            ip = ipaddress.ip_address(hostname_lower)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False
            return True
        except ValueError:
            pass  # Domain name

        # DNS resolution check
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            for addr in addr_info:
                ip_str = addr[4][0]
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                    return False
        except (socket.gaierror, socket.herror, TimeoutError):
            pass

        return True
    except Exception:
        return False



def convert_document_to_markdown(file_path: str) -> str:
    """Convert file (PDF, Office, CSV, text, etc.) to markdown using anydoc with plain-text fallback."""
    import os
    import anydoc

    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".txt", ".md", ".log", ".json", ".xml", ".yaml", ".yml"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            pass

    try:
        return anydoc.to_markdown(file_path)
    except Exception as e:
        print(f"[DEBUG] anydoc.to_markdown failed ({e}), falling back to direct text read")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def format_timestamp(seconds: float) -> str:
    """Format seconds into [HH:MM:SS] or [MM:SS] timestamp string."""
    secs = max(0, int(seconds))
    hrs = secs // 3600
    mins = (secs % 3600) // 60
    rem_secs = secs % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{rem_secs:02d}"
    return f"{mins:02d}:{rem_secs:02d}"


def format_whisper_segments(response_json: dict, offset_seconds: float = 0.0) -> str:
    """Extract transcript with timestamps from Groq Whisper verbose_json response."""
    segments = response_json.get("segments", [])
    if segments:
        lines = []
        for seg in segments:
            start_time = offset_seconds + float(seg.get("start", 0.0))
            text = seg.get("text", "").strip()
            if text:
                lines.append(f"[{format_timestamp(start_time)}] {text}")
        if lines:
            return "\n".join(lines) + "\n"
    raw_text = response_json.get("text", "").strip()
    if raw_text:
        return f"[{format_timestamp(offset_seconds)}] {raw_text}\n"
    return ""


def is_explicit_summary_request(text: str) -> bool:
    """Check if plain text explicitly requests a structured article summary or is a pasted long article."""
    t = text.strip()
    if not t:
        return False
    summary_prefixes = (
        "總結", "摘要", "請總結", "幫我總結", "請摘要", "幫我摘要",
        "做個總結", "文章摘要", "內容摘要", "重點整理",
        "tldr", "tl;dr", "summarize", "summary:"
    )
    first_line = t.split("\n", 1)[0].strip().lower()
    for kw in summary_prefixes:
        if first_line.startswith(kw) or first_line.endswith(kw):
            return True
    if len(t) >= 600 and ("\n\n" in t or t.count("。") >= 4):
        return True
    return False


def is_wiki_or_report_request(text: str) -> bool:
    """Check if user explicitly asked to use wiki or requested a report/dialogue/tutorial."""
    t = text.lower()
    wiki_triggers = ("wiki", "維基", "david888", "888wiki")
    if any(k in t for k in wiki_triggers):
        return True
    report_triggers = (
        "分析", "報告", "研究", "整理", "比較", "架構", "教學", "口說",
        "對話", "簡報", "投影片", "教案", "企劃", "範例", "大綱",
        "report", "analysis", "guide", "overview", "dialogue", "presentation"
    )
    return any(k in t for k in report_triggers)


def sanitize_model_output(text: str) -> tuple[str, str]:
    """Extract clean content and potential title from model output if it contains pseudo tool call tokens like [CALL:/wiki {...}]."""
    import json
    t = text.strip()
    if "[CALL:" in t:
        match = re.search(r"\[CALL:[^\{]*(\{.*\})\s*\]", t, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                data = json.loads(json_str, strict=False)
                content = data.get("content") or data.get("text") or ""
                title = data.get("title") or data.get("slug") or ""
                if content:
                    return content, title
            except Exception:
                pass
    return t, ""


def is_conversation_followup(text: str, history: dict | None) -> bool:
    """Check if the user input is genuinely asking follow-up questions about a previous summary."""
    if not history or not history.get("summary"):
        return False
    t = text.strip().lower()
    if is_url(t) or is_explicit_summary_request(t) or is_wiki_or_report_request(t):
        return False
    # If the text explicitly starts with creative/generation commands, it's not a followup to the old summary
    if any(t.startswith(k) for k in ("寫", "幫我寫", "請寫", "製作", "生成", "translate", "write", "create")):
        return False
    referring_words = ("這篇", "文中", "作者", "上面", "剛剛", "影片", "文章", "內容", "他說", "提到", "第一點", "第二點", "這個總結")
    if any(k in t for k in referring_words):
        return True
    return len(t) < 300
