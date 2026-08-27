"""Content classification and extraction helpers."""

import re


def split_user_input(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]


def is_url(text: str) -> bool:
    return bool(re.compile(r"https?://\S+|www\.\S+").match(text))


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
