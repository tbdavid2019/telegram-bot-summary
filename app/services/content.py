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



_magika_instance = None


def get_magika():
    """Lazy initialize and return singleton Magika instance."""
    global _magika_instance
    if _magika_instance is None:
        try:
            from magika import Magika

            _magika_instance = Magika()
        except Exception as e:
            print(f"[WARN] Failed to initialize Magika ({e})")
            return None
    return _magika_instance


def detect_file_type(file_path: str) -> dict:
    """Detect file type, group, and MIME info using Google Magika (local CPU model inference).

    Returns a dict with keys:
        - label (str): canonical label, e.g. 'pdf', 'docx', 'mp3', 'txt', 'python'
        - mime_type (str): MIME type, e.g. 'application/pdf', 'audio/mpeg'
        - group (str): content category, e.g. 'document', 'audio', 'video', 'code', 'text', 'archive'
        - description (str): human-readable format description
        - extensions (list[str]): recommended file extensions
        - is_text (bool): whether the content is plain text / code
        - score (float): model confidence score (0.0 - 1.0)
    """
    m = get_magika()
    if m is not None:
        try:
            from pathlib import Path

            res = m.identify_path(Path(file_path))
            if getattr(res, "ok", False):
                out = res.output
                return {
                    "label": getattr(out, "label", "unknown"),
                    "mime_type": getattr(out, "mime_type", "application/octet-stream"),
                    "group": getattr(out, "group", "unknown"),
                    "description": getattr(out, "description", ""),
                    "extensions": list(getattr(out, "extensions", [])),
                    "is_text": getattr(out, "is_text", False),
                    "score": getattr(res, "score", 1.0),
                }
        except Exception as e:
            print(f"[DEBUG] Magika identify_path failed ({e}), falling back to extension detection")

    # Fallback when Magika is unavailable or encounters error
    import mimetypes
    import os

    ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    mime, _ = mimetypes.guess_type(file_path)
    is_txt = ext in ("txt", "md", "csv", "json", "py", "xml", "log", "yaml", "yml", "ini", "sh", "js", "html", "css")
    return {
        "label": ext or "unknown",
        "mime_type": mime or ("text/plain" if is_txt else "application/octet-stream"),
        "group": "text" if is_txt else ("document" if ext in ("pdf", "docx", "pptx", "xlsx", "epub") else "unknown"),
        "description": "Fallback mime guess",
        "extensions": [ext] if ext else [],
        "is_text": is_txt,
        "score": 0.0,
    }


def transcribe_local_audio(file_path: str) -> str:
    """Transcribe local audio file using Groq Whisper API (whisper-large-v3) with timestamped segments."""
    import json
    import os
    import subprocess
    import uuid
    from pydub import AudioSegment

    audio_file = AudioSegment.from_file(file_path)
    chunk_size = 100 * 1000  # 100 seconds
    chunks = [audio_file[i : i + chunk_size] for i in range(0, len(audio_file), chunk_size)]

    groq_key = (os.environ.get("GROQ_API_KEY") or "").split(",")[0].strip() or "YOUR_GROQ_API_KEY"
    asr_timeout = int(os.environ.get("ASR_TIMEOUT_SECONDS", "180"))

    transcript = ""
    created_temp_files = []
    try:
        for i, chunk in enumerate(chunks):
            temp_file_path = f"/tmp/{uuid.uuid4()}.wav"
            created_temp_files.append(temp_file_path)
            chunk.export(temp_file_path, format="wav")
            offset_seconds = i * (chunk_size / 1000.0)

            curl_command = [
                "curl",
                "https://api.groq.com/openai/v1/audio/transcriptions",
                "-H",
                f"Authorization: Bearer {groq_key}",
                "-H",
                "Content-Type: multipart/form-data",
                "-F",
                f"file=@{temp_file_path}",
                "-F",
                "model=whisper-large-v3",
                "-F",
                "response_format=verbose_json",
            ]

            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=asr_timeout)
            try:
                response_json = json.loads(result.stdout)
                chunk_transcript = format_whisper_segments(response_json, offset_seconds=offset_seconds)
                transcript += chunk_transcript if chunk_transcript else response_json.get("text", "") + "\n"
            except (KeyError, json.JSONDecodeError) as e:
                print(f"[ERROR] Error decoding transcription response for chunk {i}: {e}")
    finally:
        for tmp in created_temp_files:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

    return transcript.strip()


def convert_document_to_markdown(file_path: str) -> str:
    """Convert file (PDF, Office, CSV, text, etc.) to markdown using Magika content detection & anydoc with plain-text fallback."""
    import os
    import anydoc

    file_info = detect_file_type(file_path)
    is_text = file_info.get("is_text", False)
    group = file_info.get("group", "")
    label = file_info.get("label", "")
    ext = os.path.splitext(file_path)[1].lower()

    # If it's plain text or source code, read directly as text
    if is_text or group in ("text", "code") or ext in (".txt", ".md", ".log", ".json", ".xml", ".yaml", ".yml", ".py", ".sh", ".js", ".html", ".css", ".sql", ".ini", ".env", ".csv"):
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if content.strip():
                    return content
        except Exception:
            pass

    # Unsupported executable or archive files
    if group in ("executable", "archive") and ext not in (".docx", ".pptx", ".xlsx", ".epub", ".pdf"):
        raise ValueError(f"不支援的檔案格式：{file_info.get('description', '')} ({label})。請提供文字、PDF 或 Office 辦公文件。")

    # If file lacks extension, provide extension hint via temporary symlink so anydoc detects format
    resolved_path = file_path
    temp_symlink = None
    if not ext and file_info.get("extensions"):
        primary_ext = "." + file_info["extensions"][0]
        temp_symlink = f"{file_path}{primary_ext}"
        try:
            if not os.path.exists(temp_symlink):
                os.symlink(file_path, temp_symlink)
            resolved_path = temp_symlink
        except Exception:
            resolved_path = file_path

    try:
        return anydoc.to_markdown(resolved_path)
    except Exception as e:
        needs_ocr_cls = getattr(anydoc, "NeedsOcrError", None)
        if needs_ocr_cls is not None and isinstance(e, needs_ocr_cls):
            raise ValueError("此 PDF 為掃描影像檔（無內嵌文字層），目前無法直接提取文字。") from e
        print(f"[DEBUG] anydoc.to_markdown failed ({e}), falling back to direct text read")
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    finally:
        if temp_symlink and os.path.islink(temp_symlink):
            try:
                os.unlink(temp_symlink)
            except Exception:
                pass


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


_INVALID_RAW_TITLES = {
    "影片",
    "無法提取標題",
    "無法下載該網頁的內容。",
    "抓取過程中發生錯誤。",
    "短文之摘要",
    "text summary",
    "youtube",
    "twitter",
    "x",
    "facebook",
    "tiktok",
    "instagram",
}

_SUMMARY_BOT_TAGLINE = "✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡"

_TITLE_LINE_PATTERN = re.compile(
    r"^(?:#{1,6}\s*)?(?:[*_]{1,2}\s*)?(?:seo\s*標題|標題|title)(?:\s*[*_]{1,2})?\s*[:：]\s*(.*?)\s*$",
    re.IGNORECASE,
)


def sanitize_raw_title(title: str | None, max_length: int = 200) -> str:
    """Remove control characters, collapse newlines/whitespace, and truncate to max_length."""
    if not title or not isinstance(title, str):
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if max_length > 0 and len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip()
    return cleaned


def is_summary_error_message(text: str | None) -> bool:
    """Return True if text is empty or represents a known summary generation error message."""
    if not text or not isinstance(text, str):
        return True
    stripped = text.strip()
    if not stripped:
        return True
    return stripped.startswith("⚠️ 摘要生成失敗") or stripped.startswith("Unknown error!")


def _split_markdown_safely(text: str, limit: int = 3200) -> list[str]:
    """Split Markdown text into chunks <= limit along paragraph, newline, sentence, or space boundaries."""
    if not text or not isinstance(text, str):
        return []
    if limit <= 0:
        return [text]
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            if remaining.strip():
                chunks.append(remaining)
            break

        window = remaining[:limit]
        split_at = -1
        advance_from = -1

        # 1. Paragraph boundary (\n\n)
        pos = window.rfind("\n\n")
        if pos > 0:
            split_at = pos
            advance_from = pos + 2

        # 2. Line boundary (\n)
        if split_at <= 0:
            pos = window.rfind("\n")
            if pos > 0:
                split_at = pos
                advance_from = pos + 1

        # 3. Sentence punctuation or space boundary
        if split_at <= 0:
            best_punct = -1
            for punct in ("。", "！", "？", ". ", "! ", "? "):
                p_idx = window.rfind(punct)
                if p_idx > best_punct:
                    best_punct = p_idx
                    split_at = p_idx + 1
                    advance_from = p_idx + len(punct)
            if split_at <= 0:
                for ws in (" ", "\t"):
                    w_idx = window.rfind(ws)
                    if w_idx > split_at:
                        split_at = w_idx
                        advance_from = w_idx + 1

        # 4. Hard split fallback
        if split_at <= 0:
            split_at = limit
            advance_from = limit

        chunk = remaining[:split_at].rstrip("\n")
        if chunk:
            chunks.append(chunk)
        next_remaining = remaining[advance_from:].lstrip("\n")
        if len(next_remaining) >= len(remaining):
            # Guarantee forward progress even on edge-case leading newlines
            next_remaining = remaining[limit:]
        remaining = next_remaining

    return chunks


def needs_title_localization(title: str, target_lang: str = "zh-TW") -> bool:
    """Check whether a video/webpage title is in a foreign language and needs localization into Traditional Chinese."""
    if not title or not isinstance(title, str):
        return False
    t = title.strip()
    if len(t) < 2:
        return False

    if t.lower() in _INVALID_RAW_TITLES:
        return False

    # If title contains Japanese Kana (Hiragana / Katakana) or Korean Hangul
    has_japanese_kana = bool(re.search(r"[\u3040-\u309f\u30a0-\u30ff]", t))
    has_korean = bool(re.search(r"[\uac00-\ud7af]", t))
    # Standard CJK Unified Ideographs (Chinese characters)
    has_chinese_chars = bool(re.search(r"[\u4e00-\u9fa5]", t))

    if has_japanese_kana or has_korean:
        return True
    if not has_chinese_chars:
        return True
    return False


def localize_title(title: str, target_lang: str = "zh-TW") -> str:
    """
    Localize foreign titles into fluent Traditional Chinese (zh-TW).
    Preserves original title: e.g. "誰是史上最有錢的人？ (¿Quién ha sido el más RICO de la historia?)"
    """
    if not needs_title_localization(title, target_lang):
        return title

    clean_title = title.strip()
    prompt = (
        f"請將以下影片/文章標題翻譯為流暢自然的繁體中文（台灣）：\n"
        f"「{clean_title}」\n\n"
        f"規則：\n"
        f"1. 直接輸出翻譯後的繁體中文標題。\n"
        f"2. 不要加上引號、括號說明、前綴或任何多餘文字。\n"
        f"3. 保持簡潔有力、符合中文語意習慣。"
    )
    try:
        from app.services.llm import call_llm_with_fallback
        translated = call_llm_with_fallback(prompt)
        if translated:
            translated = translated.strip().strip('"\'“”「」')
            # Verify translation did not fail or return generic error
            if (
                translated
                and not translated.startswith("Unknown error")
                and not translated.startswith("❌")
                and translated != clean_title
            ):
                return f"{translated} ({clean_title})"
    except Exception as e:
        print(f"[WARN] Failed to localize title '{clean_title}': {e}")

    return title


def is_valid_raw_title(title: str | None) -> bool:
    """Return True if raw title is a meaningful non-placeholder title string."""
    cleaned = sanitize_raw_title(title, max_length=0)
    if len(cleaned) < 2 or len(cleaned) > 300:
        return False
    return cleaned.lower() not in _INVALID_RAW_TITLES


def _clean_extracted_title(raw_title: str) -> str:
    """Strip surrounding quotes, paired markdown emphasis markers, and leading pins/hashes from a title."""
    clean = raw_title.strip()
    prev = None
    while clean != prev:
        prev = clean
        clean = clean.strip()
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
        clean = re.sub(r"__(.*?)__", r"\1", clean)
        if len(clean) >= 2 and clean.startswith("*") and clean.endswith("*"):
            clean = clean[1:-1]
        clean = clean.replace("**", "")
        clean = clean.strip("\"'“”「」《》")
        clean = re.sub(r"^(?:📌|#)+\s*", "", clean)
        clean = clean.strip()
    return clean


def extract_title_from_summary(summary_text: str) -> tuple[str | None, str]:
    """Extract a leading TITLE line (strictly the first non-empty line) and return (clean_title, cleaned_body)."""
    if not summary_text or not isinstance(summary_text, str):
        return None, summary_text

    lines = summary_text.splitlines()
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        match = _TITLE_LINE_PATTERN.match(stripped)
        if not match:
            return None, summary_text

        rest_idx = idx + 1
        while rest_idx < len(lines) and not lines[rest_idx].strip():
            rest_idx += 1
        if rest_idx < len(lines) and re.match(r"^-{3,}$", lines[rest_idx].strip()):
            rest_idx += 1
            while rest_idx < len(lines) and not lines[rest_idx].strip():
                rest_idx += 1

        cleaned_body = "\n".join(lines[rest_idx:]).lstrip()
        if not cleaned_body.strip():
            return None, summary_text

        clean_title = _clean_extracted_title(match.group(1))
        if (
            not clean_title
            or len(clean_title) < 2
            or len(clean_title) > 120
            or clean_title.startswith("⚠️")
            or clean_title.startswith("❌")
            or clean_title.lower().startswith("unknown error")
        ):
            return None, cleaned_body

        return clean_title, cleaned_body

    return None, summary_text


def resolve_final_title(
    ai_title: str | None,
    raw_title: str | None,
    language: str = "zh-TW",
    default_title: str = "短文之摘要",
) -> str:
    """Resolve final display title consistently: AI SEO title -> valid sanitized raw title -> default_title."""
    clean_ai = sanitize_raw_title(ai_title)
    if clean_ai:
        return clean_ai
    if is_valid_raw_title(raw_title):
        return sanitize_raw_title(raw_title)
    return default_title


def compose_summary_with_source(
    title: str,
    summary: str,
    original_url: str | None = None,
    raw_title: str | None = None,
) -> str:
    """Format the final summary message with sanitized SEO title and optional raw title / source URL footer."""
    clean_title = sanitize_raw_title(title)
    clean_raw_title = sanitize_raw_title(raw_title)
    show_raw_title = is_valid_raw_title(clean_raw_title) and clean_raw_title != clean_title

    parts = [f"📌 {clean_title}\n\n{summary}"]
    footer_lines = []
    if show_raw_title:
        footer_lines.append(f"🏷️ 原始標題：{clean_raw_title}")
    if original_url:
        footer_lines.append(f"▶ {original_url}")

    if footer_lines:
        parts.append("\n".join(footer_lines))
    return "\n\n".join(parts)


def prepare_wiki_content(
    title: str,
    summary: str,
    original_url: str | None = None,
    raw_title: str | None = None,
) -> str:
    """Build Wiki Markdown starting with a unique H1 title, demoting body H1s, and appending source metadata."""
    clean_title = sanitize_raw_title(title) or "AI 內容深度解析"
    body = (summary or "").strip()
    if body.endswith(_SUMMARY_BOT_TAGLINE):
        body = body[: -len(_SUMMARY_BOT_TAGLINE)].rstrip()

    if body:
        body = re.sub(r"(?m)^#\s+", "## ", body)

    sections = [f"# {clean_title}"]
    if body:
        sections.append(body)

    clean_raw_title = sanitize_raw_title(raw_title)
    show_raw = is_valid_raw_title(clean_raw_title) and clean_raw_title != clean_title
    footer_lines = []
    if show_raw:
        footer_lines.append(f"🏷️ 原始標題：{clean_raw_title}")
    if original_url and original_url not in ("text input", "uploaded file"):
        footer_lines.append(f"▶ 原始連結：{original_url}")
    if footer_lines:
        sections.append("---\n\n" + "\n".join(footer_lines))

    return "\n\n".join(sections)

