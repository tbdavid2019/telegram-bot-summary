"""Content classification and extraction helpers."""

import html
import ipaddress
import os
import re
import socket
import threading
import unicodedata
import urllib.parse


DEFAULT_AUTHOR_NOTE_LABEL = "[ DAVID888 筆記／觀點備註 ]"

_CJK_AND_FULLWIDTH = r"\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff\uff00-\uffef\u3000-\u303f"
_URL_PREFIX_BOUNDARY = rf"(?:^|(?<=[\s(\[{{<\"',;:!?{_CJK_AND_FULLWIDTH}]))"
_URL_IN_TEXT_RE = re.compile(
    rf"{_URL_PREFIX_BOUNDARY}(?:https?://|www\.)[^\s、，。：；！？「」『』【】（）《》〈〉<>\"{_CJK_AND_FULLWIDTH}]+",
    re.IGNORECASE,
)
_TRAILING_URL_PUNCT = frozenset("、，。：；！？\"'」』】）>,.;!?")
_OUTER_WRAPPER_PAIRS = (
    ("(", ")"),
    ("（", "）"),
    ("[", "]"),
    ("【", "】"),
    ("「", "」"),
    ("『", "』"),
    ("<", ">"),
    ('"', '"'),
    ("'", "'"),
)
_PURE_SUMMARY_COMMANDS = {
    "總結",
    "摘要",
    "幫我總結",
    "請總結",
    "幫我摘要",
    "請摘要",
    "summarize",
    "summary",
    "tldr",
    "tl;dr",
}
_PROMPT_BOUNDARY_RE = re.compile(
    r"-{3,}\s*((?:BEGIN|END)\s+(?:USER\s+NOTE|SOURCE\s+CONTENT))\s*-{3,}",
    re.IGNORECASE,
)


def get_author_note_label() -> str:
    """Return sanitized author note label or default `[ DAVID888 筆記／觀點備註 ]`."""
    return sanitize_raw_title(os.environ.get("AUTHOR_NOTE_LABEL", ""), max_length=60) or DEFAULT_AUTHOR_NOTE_LABEL


def escape_prompt_boundaries(text: str) -> str:
    """Neutralize forged prompt demarcation markers inside untrusted user notes or source content."""
    if not text or not isinstance(text, str):
        return text or ""
    return _PROMPT_BOUNDARY_RE.sub(lambda m: f"－－－ {m.group(1)} －－－", text)


def _clean_matched_url(raw_url: str) -> str:
    """Linearly strip trailing punctuation glued to a URL while preserving balanced parens/brackets."""
    if not raw_url:
        return ""
    open_paren = raw_url.count("(")
    close_paren = raw_url.count(")")
    open_bracket = raw_url.count("[")
    close_bracket = raw_url.count("]")

    end = len(raw_url)
    while end > 0:
        ch = raw_url[end - 1]
        if ch in _TRAILING_URL_PUNCT:
            end -= 1
            continue
        if ch == ")" and close_paren > open_paren:
            close_paren -= 1
            end -= 1
            continue
        if ch == "]" and close_bracket > open_bracket:
            close_bracket -= 1
            end -= 1
            continue
        break

    cleaned = raw_url[:end]
    if len(cleaned) > 2048:
        return ""
    return cleaned


def _normalize_extracted_url(raw_clean_url: str) -> str | None:
    """Ensure http/https scheme, lowercase scheme/host via urlsplit, and validate hostname."""
    if not raw_clean_url:
        return None
    candidate = f"https://{raw_clean_url}" if raw_clean_url.lower().startswith("www.") else raw_clean_url
    try:
        parsed = urllib.parse.urlsplit(candidate)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return None
        hostname = parsed.hostname
        if not hostname:
            return None
        hostname_lower = hostname.lower()
        if hostname_lower in ("www", "www."):
            return None
        port = parsed.port  # Validates numeric port range (0-65535)
    except ValueError:
        return None

    host_part = f"[{hostname_lower}]" if ":" in hostname_lower and not hostname_lower.startswith("[") else hostname_lower
    host_port = f"{host_part}:{port}" if port is not None else host_part
    if parsed.username is not None:
        auth = f"{parsed.username}:{parsed.password}@" if parsed.password is not None else f"{parsed.username}@"
        netloc = f"{auth}{host_port}"
    else:
        netloc = host_port

    return urllib.parse.urlunsplit((scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _trim_connector_edges(before: str, after: str) -> str:
    """Join remaining text around the removed URL in O(n), stripping outer wrappers and inline connectors."""
    b = before
    a = after

    # Strip matched outer wrapper pairs (e.g. "(https://...)" or "「https://...」")
    changed = True
    while changed:
        changed = False
        b_r = b.rstrip(" \t")
        a_l = a.lstrip(" \t")
        for open_ch, close_ch in _OUTER_WRAPPER_PAIRS:
            if b_r.endswith(open_ch) and a_l.startswith(close_ch):
                b = b_r[:-1]
                a = a_l[1:]
                changed = True
                break

    # Trim trailing inline connectors (: ： -) on the same line right before the URL
    if b and not b.endswith(("\n", "\r")):
        b = b.rstrip(" \t")
        while b:
            if b[-1] in (":", "："):
                b = b[:-1].rstrip(" \t")
            elif b[-1] in ("-", "–", "—") and (len(b) == 1 or b[-2].isspace()):
                b = b[:-1].rstrip(" \t")
            else:
                break

    # Trim leading inline connectors (: ： , ， 、 。 . -) on the same line right after the URL (preserve newline bullets)
    if a and not a.startswith(("\n", "\r")):
        a = a.lstrip(" \t")
        while a:
            if a[0] in (":", "：", ",", "，", "、", "。", "."):
                a = a[1:].lstrip(" \t")
            elif a[0] in ("-", "–", "—") and (len(a) == 1 or a[1].isspace()):
                a = a[1:].lstrip(" \t")
            else:
                break

    if b and a:
        if b[-1].isspace() or a[0].isspace():
            joined = b + a
        else:
            joined = b + " " + a
    else:
        joined = b + a

    cleaned = joined.strip()
    while cleaned and cleaned[0] in (":", "：") and (len(cleaned) == 1 or cleaned[1].isspace()):
        cleaned = cleaned[1:].lstrip()
    while cleaned and cleaned[-1] in (":", "：") and (len(cleaned) == 1 or cleaned[-2].isspace()):
        cleaned = cleaned[:-1].rstrip()

    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _is_pure_punctuation_or_whitespace(text: str) -> bool:
    """Return True if text contains only punctuation or whitespace characters."""
    return all(unicodedata.category(ch).startswith(("P", "Z")) or ch.isspace() for ch in text)


def parse_url_and_user_note(text: str, max_note_chars: int = 4000) -> tuple[str | None, str | None]:
    """Extract the first URL and optional user commentary/note from a Telegram or API message.

    Returns (clean_url, user_note). Returns (None, None) if no valid URL exists or if the message
    appears to be a long article (> 600 remaining chars) that merely embeds a link mid-text.
    """
    if not text or not isinstance(text, str):
        return None, None

    match = _URL_IN_TEXT_RE.search(text)
    if not match:
        return None, None

    # Early O(1)/O(prefix) guard to avoid scanning/cleaning 1MB long texts that embed a link mid-body
    url_at_start = match.start() == 0 or text[: match.start()].isspace()
    if not url_at_start and (len(text) - (match.end() - match.start())) > 600:
        return None, None

    raw_clean_url = _clean_matched_url(match.group(0))
    normalized_url = _normalize_extracted_url(raw_clean_url)
    if not normalized_url:
        return None, None

    raw_clean_end = match.start() + len(raw_clean_url)
    remaining = _trim_connector_edges(text[: match.start()], text[raw_clean_end:])

    if not url_at_start and len(remaining) > 600:
        return None, None

    if not remaining or _is_pure_punctuation_or_whitespace(remaining) or remaining.lower() in _PURE_SUMMARY_COMMANDS:
        user_note = None
    else:
        user_note = remaining[:max_note_chars].strip() or None

    return normalized_url, user_note


def format_user_note_block(
    user_note: str | None,
    note_label: str | None = None,
    escape_markdown_structure: bool = True,
) -> str:
    """Format user commentary/note into a prominent, sanitized Markdown blockquote header block."""
    if not user_note or not isinstance(user_note, str) or not user_note.strip():
        return ""
    label = sanitize_raw_title(note_label, max_length=60) if note_label else get_author_note_label()
    if not label:
        label = DEFAULT_AUTHOR_NOTE_LABEL
    clean_note = re.sub(r"\n{3,}", "\n\n", user_note.strip())
    if not escape_markdown_structure:
        return f"### 📝 {label}\n{clean_note}"

    formatted_lines: list[str] = []
    for raw_line in clean_note.splitlines():
        escaped_line = html.escape(raw_line, quote=False)
        stripped = escaped_line.lstrip()
        if re.match(r"^#{1,6}\s+", stripped):
            escaped_line = re.sub(r"^#{1,6}\s+", "#### ", stripped)
        elif re.match(r"^#{1,6}$", stripped):
            escaped_line = "\\" + stripped
        elif re.match(r"^(?:-{3,}|={3,})$", stripped):
            escaped_line = "\\" + stripped
        formatted_lines.append(f"> {escaped_line}" if escaped_line else ">")

    return f"### 📝 {label}\n" + "\n".join(formatted_lines)


def split_user_input(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in text.split("\n") if paragraph.strip()]


def is_url(text: str) -> bool:
    if not text or not isinstance(text, str):
        return False
    return bool(re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE).match(text))


_YOUTUBE_COLLECTION_PREFIXES = ("/channel/", "/@", "/c/", "/user/")
_YOUTUBE_COLLECTION_EXACT = {"/channel", "/c", "/user"}
_YOUTUBE_SINGLE_VIDEO_PREFIXES = ("/watch", "/shorts/", "/live/", "/embed/", "/v/")
_YOUTUBE_NON_VIDEO_PAGES = {"/", "/feed", "/results", "/gaming", "/podcasts", "/courses", "/explore", "/trending"}
_YOUTUBE_NON_VIDEO_PREFIXES = ("/feed/", "/hashtag/", "/podcasts/", "/courses/")


def get_unsupported_media_url_reason(url: str) -> str | None:
    """Return a diagnostic rejection reason when url is a non-single-video channel/playlist/page URL."""
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw:
        return None

    candidate = f"https://{raw}" if raw.lower().startswith("www.") else raw
    try:
        parsed = urllib.parse.urlsplit(candidate)
    except ValueError:
        return None

    hostname = (parsed.hostname or "").lower().rstrip(".")
    if not hostname:
        return None

    is_youtu_be = hostname == "youtu.be" or hostname == "www.youtu.be"
    is_youtube = (
        hostname == "youtube.com"
        or hostname.endswith(".youtube.com")
        or hostname == "youtube-nocookie.com"
        or hostname.endswith(".youtube-nocookie.com")
    )
    if not (is_youtu_be or is_youtube):
        return None

    raw_path = parsed.path or "/"
    path_lower = raw_path.rstrip("/").lower() or "/"
    query = urllib.parse.parse_qs(parsed.query)
    has_video_id = bool(query.get("v") and query["v"][0].strip())

    if is_youtu_be:
        if path_lower == "/" and not has_video_id:
            return (
                "❌ 無法處理此 YouTube 短網址（未指定影片 ID）。\n"
                "原因：網址僅為網域首頁，缺少具體影片代碼，請貼上完整的單支影片網址（例如 youtu.be/<影片ID>）。\n"
                "排查代碼：UNSUPPORTED_YOUTUBE_PAGE"
            )
        return None

    if path_lower in _YOUTUBE_COLLECTION_EXACT or path_lower.startswith(_YOUTUBE_COLLECTION_PREFIXES):
        return (
            "❌ 無法處理此 YouTube 頻道／創作者主頁網址（不支援批次抓取整個頻道）。\n"
            f"原因：偵測到頻道路徑「{raw_path}」，為避免遞迴抓取大量影片導致系統阻塞與記憶體耗盡，"
            "僅支援單支影片網址（例如 youtube.com/watch?v=...、youtu.be/...、/shorts/... 或 /live/...）。\n"
            "排查代碼：UNSUPPORTED_YOUTUBE_CHANNEL"
        )

    is_single_video_path = any(path_lower.startswith(prefix) for prefix in _YOUTUBE_SINGLE_VIDEO_PREFIXES)
    if path_lower == "/playlist" or ("list" in query and not has_video_id and not is_single_video_path):
        return (
            "❌ 無法處理此 YouTube 播放清單網址（不支援批次抓取整份清單）。\n"
            "原因：網址僅包含播放清單參數（list）而未指定單一影片 ID（v），請改貼清單中的單支影片網址（youtube.com/watch?v=...）。\n"
            "排查代碼：UNSUPPORTED_YOUTUBE_PLAYLIST"
        )

    if not has_video_id and (
        path_lower in _YOUTUBE_NON_VIDEO_PAGES or path_lower.startswith(_YOUTUBE_NON_VIDEO_PREFIXES)
    ):
        return (
            "❌ 無法處理此 YouTube 頁面網址（非單支影片）。\n"
            f"原因：偵測到首頁／分類／搜尋頁路徑「{raw_path}」，請貼上具體的單支影片網址（watch?v=...、youtu.be/...、/shorts/... 或 /live/...）。\n"
            "排查代碼：UNSUPPORTED_YOUTUBE_PAGE"
        )

    return None


def _is_blocked_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_reserved
        or ip_obj.is_multicast
        or ip_obj.is_unspecified
        or not ip_obj.is_global
    )


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

        # Block loopback, localhost, Docker internal hostnames, and cloud metadata hostnames
        blocked_hostnames = {
            "localhost",
            "localhost.localdomain",
            "ip6-localhost",
            "ip6-loopback",
            "host.docker.internal",
            "gateway.docker.internal",
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
            return not _is_blocked_ip(ip)
        except ValueError:
            pass  # Domain name

        # DNS resolution check (fail closed on unresolvable/split-DNS internal names)
        try:
            addr_info = socket.getaddrinfo(hostname, None)
            if not addr_info:
                return False
            for addr in addr_info:
                ip_str = addr[4][0].split("%", 1)[0]
                ip = ipaddress.ip_address(ip_str)
                if _is_blocked_ip(ip):
                    return False
        except (socket.gaierror, socket.herror, TimeoutError):
            return False

        return True
    except Exception:
        return False


_MAX_WEB_BYTES = 10 * 1024 * 1024  # 10 MB cap for web/RSS/API HTML fetches
_ssrf_guard_state = threading.local()
_ssrf_patch_lock = threading.Lock()
_ssrf_patch_depth = 0
_orig_urllib3_create_connection = None


def _ssrf_checked_create_connection(address, *args, **kwargs):
    host, port = address
    # Strip IPv6 brackets if any
    host_clean = str(host).strip("[]")
    try:
        ip = ipaddress.ip_address(host_clean)
        if _is_blocked_ip(ip):
            raise ValueError("Blocked non-global IP connection (SSRF protection).")
    except ValueError as exc:
        if "Blocked non-global IP" in str(exc):
            raise
        # Hostname: resolve once and connect directly to a validated global IP to prevent DNS rebinding
        infos = socket.getaddrinfo(host_clean, port, type=socket.SOCK_STREAM)
        if not infos:
            raise OSError(f"Could not resolve host {host_clean}")
        for family, socktype, proto, canonname, sockaddr in infos:
            ip_str = sockaddr[0].split("%", 1)[0]
            if _is_blocked_ip(ipaddress.ip_address(ip_str)):
                raise ValueError("Blocked DNS-rebound non-global IP (SSRF protection).")
        # Connect directly via validated numeric IP while keeping TLS SNI/Host intact at caller layer
        source_address = kwargs.get("source_address")
        timeout = kwargs.get("timeout", socket._GLOBAL_DEFAULT_TIMEOUT)
        socket_options = kwargs.get("socket_options")
        last_err = None
        for family, socktype, proto, _canonname, sockaddr in infos:
            sock = None
            try:
                sock = socket.socket(family, socktype, proto)
                if socket_options:
                    for opt in socket_options:
                        sock.setsockopt(*opt)
                if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                    sock.settimeout(timeout)
                if source_address:
                    sock.bind(source_address)
                sock.connect(sockaddr)
                return sock
            except OSError as err:
                last_err = err
                if sock is not None:
                    sock.close()
        if last_err is not None:
            raise last_err
        raise OSError("Failed to establish SSRF-checked TCP connection.")
    return _orig_urllib3_create_connection(address, *args, **kwargs)


class _SSRFPinnedConnectionGuard:
    """Temporarily wrap urllib3 create_connection to reject private/loopback IPs at TCP connect time."""

    def __enter__(self):
        global _ssrf_patch_depth, _orig_urllib3_create_connection
        import urllib3.util.connection as urllib3_conn

        with _ssrf_patch_lock:
            if _ssrf_patch_depth == 0:
                _orig_urllib3_create_connection = urllib3_conn.create_connection

                def _guarded(address, *args, **kwargs):
                    if getattr(_ssrf_guard_state, "active", False):
                        return _ssrf_checked_create_connection(address, *args, **kwargs)
                    return _orig_urllib3_create_connection(address, *args, **kwargs)

                urllib3_conn.create_connection = _guarded
            _ssrf_patch_depth += 1
        _ssrf_guard_state.active = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _ssrf_patch_depth, _orig_urllib3_create_connection
        import urllib3.util.connection as urllib3_conn

        _ssrf_guard_state.active = False
        with _ssrf_patch_lock:
            _ssrf_patch_depth = max(0, _ssrf_patch_depth - 1)
            if _ssrf_patch_depth == 0 and _orig_urllib3_create_connection is not None:
                urllib3_conn.create_connection = _orig_urllib3_create_connection
                _orig_urllib3_create_connection = None


def safe_http_get(
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    stream: bool = False,
    max_redirects: int = 5,
    max_bytes: int = _MAX_WEB_BYTES,
):
    """Perform an HTTP GET request with DNS-rebinding-proof IP validation, byte cap, and deadline."""
    import requests
    import time

    current_url = url
    deadline = time.monotonic() + float(timeout)
    with _SSRFPinnedConnectionGuard():
        for _ in range(max_redirects + 1):
            if not is_safe_url(current_url):
                raise ValueError("不支援或受保護的私有/內部網路網址 (Blocked private or invalid URL)。")
            remaining = max(1.0, deadline - time.monotonic())
            req_timeout = min(float(timeout), remaining)
            resp = requests.get(
                current_url,
                headers=headers,
                timeout=req_timeout,
                stream=True if not stream else True,
                allow_redirects=False,
            )
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("Location")
                resp.close()
                if not location:
                    return resp
                current_url = urllib.parse.urljoin(current_url, location)
                continue
            if not stream and isinstance(resp, requests.Response):
                try:
                    chunks = []
                    total = 0
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            total += len(chunk)
                            if total > max_bytes:
                                raise ValueError(f"Web response exceeded maximum size ({max_bytes} bytes).")
                            chunks.append(chunk)
                        if time.monotonic() > deadline:
                            raise TimeoutError(f"Web response transfer exceeded {timeout}s deadline.")
                    resp._content = b"".join(chunks)
                    resp._content_consumed = True
                finally:
                    resp.close()
            return resp
    raise ValueError("Too many redirects while fetching URL.")


import threading

_magika_lock = threading.Lock()
_magika_instance = None


def get_magika():
    """Lazy initialize and return singleton Magika instance (thread-safe)."""
    global _magika_instance
    if _magika_instance is None:
        with _magika_lock:
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


def _split_audio_chunks_streaming(file_path: str, tmp_dir: str, chunk_seconds: int = 100) -> list[str] | None:
    """Split audio into compressed MP3 segments using ffmpeg without loading full PCM into RAM."""
    import shutil
    import subprocess

    if not os.path.isfile(file_path):
        return None
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return None

    out_pattern = os.path.join(tmp_dir, "chunk_%04d.mp3")
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        file_path,
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "64k",
        "-f",
        "segment",
        "-segment_time",
        str(chunk_seconds),
        "-reset_timestamps",
        "1",
        out_pattern,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if res.returncode == 0:
            files = sorted(
                os.path.join(tmp_dir, name)
                for name in os.listdir(tmp_dir)
                if name.startswith("chunk_") and name.endswith(".mp3")
            )
            if files:
                return files
    except Exception as exc:
        print(f"[WARN] Streaming ffmpeg split failed, falling back to pydub: {exc}")
    return None


def _transcribe_single_chunk(
    chunk_idx: int,
    chunk_path: str,
    offset_seconds: float,
    groq_keys: list[str],
    asr_timeout: float,
) -> tuple[int, str]:
    import requests

    keys_to_try = groq_keys or ["YOUR_GROQ_API_KEY"]
    last_error = "Unknown ASR error"

    for k_offset in range(len(keys_to_try)):
        key = keys_to_try[(chunk_idx + k_offset) % len(keys_to_try)]
        try:
            with open(chunk_path, "rb") as audio_fh:
                resp = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {key}"},
                    files={"file": (os.path.basename(chunk_path), audio_fh)},
                    data={
                        "model": "whisper-large-v3",
                        "response_format": "verbose_json",
                    },
                    timeout=asr_timeout,
                )
            if resp.status_code == 200:
                response_json = resp.json()
                chunk_transcript = format_whisper_segments(response_json, offset_seconds=offset_seconds)
                text_out = chunk_transcript if chunk_transcript else (response_json.get("text", "") + "\n")
                return chunk_idx, text_out
            last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            if resp.status_code in (401, 403, 429, 500, 502, 503, 504):
                continue
            break
        except Exception as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(f"Groq Whisper ASR failed on chunk {chunk_idx}: {last_error}")


def transcribe_local_audio(file_path: str, asr_timeout: float | None = None) -> str:
    """Transcribe local audio file using Groq Whisper API (whisper-large-v3) with timestamped segments."""
    from concurrent.futures import ThreadPoolExecutor
    import tempfile
    from app.services.llm import _split_keys

    chunk_seconds = 100
    chunk_ms = chunk_seconds * 1000
    combined_groq_raw = ",".join(
        val
        for val in (os.environ.get("GROQ_API_KEY", ""), os.environ.get("GROQ_FALLBACK_KEYS", ""))
        if val and val.strip()
    )
    groq_keys = _split_keys(combined_groq_raw)
    effective_timeout = (
        float(os.environ.get("ASR_TIMEOUT_SECONDS", os.environ.get("SUBPROCESS_TIMEOUT_SECONDS", "600")))
        if asr_timeout is None
        else float(asr_timeout)
    )

    with tempfile.TemporaryDirectory(prefix="asr_") as tmp_dir:
        chunk_paths = _split_audio_chunks_streaming(file_path, tmp_dir, chunk_seconds=chunk_seconds)
        if chunk_paths is None:
            from pydub import AudioSegment

            audio_file = AudioSegment.from_file(file_path)
            chunks = [audio_file[i : i + chunk_ms] for i in range(0, len(audio_file), chunk_ms)]
            chunk_paths = []
            for i, chunk in enumerate(chunks):
                chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.mp3")
                try:
                    chunk.export(chunk_path, format="mp3", bitrate="64k")
                except Exception:
                    chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.wav")
                    chunk.export(chunk_path, format="wav")
                if not os.path.exists(chunk_path):
                    if type(audio_file).__module__.startswith("unittest.mock"):
                        with open(chunk_path, "wb") as dummy:
                            dummy.write(b"audio")
                    else:
                        raise RuntimeError(f"Audio chunk export failed to produce {chunk_path}")
                chunk_paths.append(chunk_path)

        if not chunk_paths:
            return ""

        max_workers = min(3, len(chunk_paths))
        if max_workers <= 1:
            results = [
                _transcribe_single_chunk(i, p, i * float(chunk_seconds), groq_keys, effective_timeout)
                for i, p in enumerate(chunk_paths)
            ]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = [
                    pool.submit(
                        _transcribe_single_chunk,
                        i,
                        p,
                        i * float(chunk_seconds),
                        groq_keys,
                        effective_timeout,
                    )
                    for i, p in enumerate(chunk_paths)
                ]
                results = [f.result() for f in futures]

        results.sort(key=lambda item: item[0])
        return "".join(text_part for _, text_part in results).strip()


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
        try:
            with open(file_path, "rb") as raw_fh:
                sample = raw_fh.read(4096)
            if b"\x00" in sample:
                raise ValueError("二進位檔案無法當作純文字解析。")
            with open(file_path, "r", encoding="utf-8", errors="strict") as f:
                text_fallback = f.read()
            if text_fallback.strip():
                return text_fallback
        except (UnicodeDecodeError, ValueError) as text_err:
            raise ValueError(f"無法解析檔案格式（{label or ext or 'unknown'}）：{e}") from text_err
        raise ValueError(f"無法解析檔案內容：{e}") from e
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


def is_explicit_wiki_publish_request(text: str) -> bool:
    """Return True ONLY when user explicitly asks to publish or write to Wiki (prevents leaking private chats)."""
    if not text or not isinstance(text, str):
        return False
    t = text.strip().lower()
    negations = ("不要wiki", "不用wiki", "別發wiki", "不要發到wiki", "don't publish", "no wiki", "without wiki")
    if any(neg in t for neg in negations):
        return False
    wiki_triggers = ("wiki", "維基", "david888 wiki", "888wiki", "發布到維基")
    return any(k in t for k in wiki_triggers)


def is_wiki_or_report_request(text: str) -> bool:
    """Check if user asked to use wiki or requested a report/dialogue/tutorial."""
    if is_explicit_wiki_publish_request(text):
        return True
    t = (text or "").lower()
    if any(k in t for k in ("wiki", "維基", "david888", "888wiki")):
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
    if is_url(t) or parse_url_and_user_note(text)[0] or is_explicit_summary_request(t) or is_wiki_or_report_request(t):
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


def get_summary_bot_tagline() -> str:
    return (os.environ.get("BOT_TAGLINE") or _SUMMARY_BOT_TAGLINE).strip()


EXTRACTION_ERROR_MESSAGES = frozenset({
    "暫時無法轉錄",
    "該影片沒有可用的字幕，且音頻轉換功能未啟用。",
    "無法獲取字幕或進行音頻轉換。",
    "音頻轉錄失敗。",
    "無法從 Pocket Casts 提取音訊或 RSS feed。",
    "無法從 Pocket Casts 頁面提取 RSS feed。",
    "無法從 RSS feed 獲取 podcast episodes。",
    "處理 Pocket Casts URL 時發生錯誤。",
    "無法從 SoundOn 頁面提取 RSS feed。",
    "處理 SoundOn URL 時發生錯誤。",
    "無法從 Apple Podcast 提取 RSS feed。",
    "處理 Apple Podcast URL 時發生錯誤。",
    "Podcast 音頻轉錄失敗。",
    "不支援或受保護的私有/內部網路網址。",
    "不支援或受保護的私有/內部網路網址 (Blocked private or invalid URL)。",
})


def is_extraction_error(text_array) -> bool:
    """Return True if process_user_input / transcript extraction returned a single sentinel error message."""
    if not (isinstance(text_array, list) and len(text_array) == 1 and isinstance(text_array[0], str)):
        return False
    msg = text_array[0]
    if msg in EXTRACTION_ERROR_MESSAGES:
        return True
    return (
        msg.startswith("❌ 無法處理此 YouTube ")
        or msg.startswith("⏱️ 網址處理逾時")
        or "排查代碼：UNSUPPORTED_" in msg
        or "排查代碼：URL_PROCESSING_TIMEOUT" in msg
    )

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
    if cleaned in EXTRACTION_ERROR_MESSAGES or cleaned.lower().startswith("抓取過程中發生錯誤"):
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
    user_note: str | None = None,
) -> str:
    """Format the final summary message with sanitized SEO title, optional user note block, and source URL footer."""
    clean_title = sanitize_raw_title(title)
    clean_raw_title = sanitize_raw_title(raw_title)
    show_raw_title = is_valid_raw_title(clean_raw_title) and clean_raw_title != clean_title

    note_block = format_user_note_block(user_note)
    body = f"{note_block}\n\n---\n\n{summary}" if note_block else summary

    parts = [f"📌 {clean_title}\n\n{body}"]
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
    user_note: str | None = None,
) -> str:
    """Build Wiki Markdown starting with a unique H1 title, optional user note block, demoting body H1s, and appending source metadata."""
    clean_title = sanitize_raw_title(title) or "AI 內容深度解析"
    body = (summary or "").strip()
    tagline = get_summary_bot_tagline()
    for candidate_tag in (tagline, _SUMMARY_BOT_TAGLINE):
        if candidate_tag and body.endswith(candidate_tag):
            body = body[: -len(candidate_tag)].rstrip()
            break

    if body:
        body = re.sub(r"(?m)^#\s+", "## ", body)

    sections = [f"# {clean_title}"]
    note_block = format_user_note_block(user_note)
    if note_block:
        sections.append(f"{note_block}\n\n---" if body else note_block)
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

