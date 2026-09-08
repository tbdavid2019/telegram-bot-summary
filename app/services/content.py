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
