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
