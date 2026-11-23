import yt_dlp
import glob
import html
import io
import json
import logging
import os
import pickle
import re
import shutil
import smtplib
import tempfile
import threading
import time
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import asyncio
import markdown
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PicklePersistence,
    filters,
)
import uvicorn

from app.config import (
    get_bot_display_name,
    get_data_dir,
    get_mongo_client,
    get_support_contact,
    is_admin_user,
)
from app.repositories.summaries import SummaryRepository
from app.runtime import run_blocking
from app.services.api_keys import (
    KeyAlreadyExistsError,
    KeyNotFoundError,
    build_curl_usage_guide,
    get_api_key_manager,
    is_telegram_user_allowed,
    resolve_api_base_url,
)
from app.services.box import (
    get_box_stats,
    upload_file_to_box,
    upload_url_to_box,
)
from app.services.content import (
    EXTRACTION_ERROR_MESSAGES,
    _split_markdown_safely,
    classify_extraction_failure,
    compose_summary_with_source,
    convert_document_to_markdown,
    detect_file_type,
    escape_prompt_boundaries,
    format_timestamp,
    format_whisper_segments,
    get_unsupported_media_url_reason,
    is_conversation_followup,
    is_explicit_summary_request,
    is_explicit_wiki_publish_request,
    is_extraction_error,
    is_safe_url,
    is_summary_error_message,
    is_url,
    is_valid_raw_title,
    is_wiki_or_report_request,
    localize_title,
    needs_title_localization,
    parse_url_and_user_note,
    parse_urls_and_user_note,
    prepare_wiki_content,
    resolve_final_title,
    safe_http_get,
    sanitize_model_output,
    sanitize_raw_title,
    split_user_input,
    transcribe_local_audio,
)
from app.services.decision import (
    CLEF_TIMEOUT_SECONDS,
    is_advertisement_content,
    is_decision_ad_filter_enabled,
)
from app.services.divination import (
    TAROT_HELP_TEXT,
    YINYUAN_HELP_TEXT,
    ask_tarot_api,
    ask_yinyuan_api,
    format_tarot_reply,
    format_yinyuan_reply,
    parse_tarot_command,
    parse_yinyuan_command,
)
from app.services.llm import (
    LLMEndpoint,
    call_llm_with_fallback,
    get_available_models,
    get_configured_endpoints,
)
from app.services.podcast import (
    download_and_transcribe_podcast,
    extract_episode_from_apple_podcast,
    extract_pocketcasts_episode,
    extract_rss_from_apple_podcast,
    extract_rss_from_pocketcasts,
    extract_rss_from_soundon,
    get_latest_podcast_episode,
    get_pocketcasts_title,
    is_apple_podcast_url,
    is_pocketcasts_url,
    is_soundon_url,
    split_transcript_lines,
)
from app.services.quick_reply import (
    build_concept_image_url,
    build_quick_reply_source,
    build_transform_prompt,
    clean_social_post_output,
    detect_quick_reply_intent,
    get_summary_quick_reply_keyboard,
)
from app.services.summarization import (
    SYSTEM_PROMPT_EN,
    SYSTEM_PROMPT_ZH,
    call_gpt_api as _service_call_gpt_api,
    summarize as _service_summarize,
    summarize_batch as _service_summarize_batch,
)
from app.services.telegram_delivery import (
    format_for_telegram,
    send_telegram_formatted,
)
from app.services.wiki import (
    publish_wiki_page,
    read_wiki_page,
)

logger = logging.getLogger(__name__)

# SMTP 設定
smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.environ.get("SMTP_PORT", 465))
smtp_user = os.environ.get("SMTP_USER", "your_email@gmail.com")
smtp_password = os.environ.get("SMTP_PASSWORD", "your_password")
smtp_cc_emails = os.environ.get("SMTP_CC_EMAILS", "").split(",")
enable_email = int(os.environ.get("ENABLE_EMAIL", 0))

# Discord 設定
discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
enable_discord_webhook = int(os.environ.get("ENABLE_DISCORD_WEBHOOK", 0))

# Timeout 設定
WEB_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("WEB_REQUEST_TIMEOUT_SECONDS", os.environ.get("HTTP_TIMEOUT_SECONDS", "60")))
LLM_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "180"))
ASR_TIMEOUT_SECONDS = float(os.environ.get("ASR_TIMEOUT_SECONDS", os.environ.get("SUBPROCESS_TIMEOUT_SECONDS", "600")))
MEDIA_DOWNLOAD_TIMEOUT_SECONDS = float(os.environ.get("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "900"))
YTDLP_PROBE_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_PROBE_TIMEOUT_SECONDS", "45"))
URL_PROCESSING_TIMEOUT_SECONDS = float(
    os.environ.get("URL_PROCESSING_TIMEOUT_SECONDS", str(int(max(ASR_TIMEOUT_SECONDS, MEDIA_DOWNLOAD_TIMEOUT_SECONDS))))
)
BOT_CONCURRENT_UPDATES = max(2, int(os.environ.get("BOT_CONCURRENT_UPDATES", "8")))
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "5000"))

# LLM 設定
llm_api_key = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY"))
model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
llm2_api_key = os.environ.get("LLM2_API_KEY", "")
llm2_model = os.environ.get("LLM2_MODEL", "")
llm2_base_url = os.environ.get("LLM2_BASE_URL", "")
use_llm2 = bool(llm2_api_key and llm2_model and llm2_base_url)

# Telegram 設定
telegram_token = os.environ.get("TELEGRAM_TOKEN", "xxx")
allowed_users = os.environ.get("ALLOWED_USERS", "")
show_processing = int(os.environ.get("SHOW_PROCESSING", "1"))

# 其他設定
lang = os.environ.get("TS_LANG", "繁體中文")
chunk_size = int(os.environ.get("CHUNK_SIZE", 2100))
use_audio_fallback = int(os.environ.get("USE_AUDIO_FALLBACK", "0"))
groq_api_key = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
ANSWER_BOOK_API = os.environ.get("ANSWER_BOOK_API", "https://answerbook.david888.com/answersOriginal")

# MongoDB 共用連線池
mongo_uri = os.environ.get("MONGO_URI", "")
mongo_client = get_mongo_client(mongo_uri, timeout_ms=MONGO_TIMEOUT_MS) if mongo_uri else None
summary_collection = mongo_client["bot_database"]["summaries"] if mongo_client is not None else None
decision_collection = mongo_client["bot_database"]["ad_decisions"] if mongo_client is not None else None
_summary_repo = SummaryRepository(collection=summary_collection)

SUPPORTED_LANGUAGES = {
    "zh-TW": "繁體中文",
    "en": "English",
}

PREFERRED_SUBTITLE_LANGS = ["zh-Hant", "zh-TW", "zh-HK", "zh-Hans", "zh-CN", "zh", "en"]
PREFERRED_AUDIO_FORMAT = (
    "bestaudio[language=zh-Hant]/bestaudio[language=zh-TW]/bestaudio[language=zh-HK]/"
    "bestaudio[language=zh]/bestaudio[language=zh-Hans]/bestaudio[language=zh-CN]/"
    "bestaudio[language=en]/bestaudio[protocol^=http]/bestaudio/best"
)

# Single-pass URL metadata/title caches to eliminate redundant yt-dlp / web fetches within a request
_META_CACHE_LOCK = threading.Lock()
_META_CACHE_TTL = 120.0
_URL_TITLE_CACHE: dict[str, tuple[float, str]] = {}
_YTDLP_INFO_CACHE: dict[str, tuple[float, dict]] = {}
_AD_HIDDEN_TTL_SECONDS = 3600.0
_MAX_AD_HIDDEN_ITEMS = 20

_resolve_final_title = resolve_final_title
_send_telegram_formatted = send_telegram_formatted


def _cache_url_title(url: str, title: str | None) -> None:
    if not url or not title or not isinstance(title, str):
        return
    clean = title.strip()
    if not clean:
        return
    now = time.monotonic()
    with _META_CACHE_LOCK:
        if len(_URL_TITLE_CACHE) >= 256:
            oldest = min(_URL_TITLE_CACHE, key=lambda k: _URL_TITLE_CACHE[k][0])
            _URL_TITLE_CACHE.pop(oldest, None)
        _URL_TITLE_CACHE[url] = (now, clean)


def _get_cached_title(url: str) -> str | None:
    now = time.monotonic()
    with _META_CACHE_LOCK:
        entry = _URL_TITLE_CACHE.get(url)
        if entry and (now - entry[0]) < _META_CACHE_TTL:
            return entry[1]
        if entry:
            _URL_TITLE_CACHE.pop(url, None)
    return None


def _cache_ytdlp_info(url: str, info: dict | None) -> None:
    if not url or not isinstance(info, dict):
        return
    now = time.monotonic()
    with _META_CACHE_LOCK:
        if len(_YTDLP_INFO_CACHE) >= 128:
            oldest = min(_YTDLP_INFO_CACHE, key=lambda k: _YTDLP_INFO_CACHE[k][0])
            _YTDLP_INFO_CACHE.pop(oldest, None)
        _YTDLP_INFO_CACHE[url] = (now, info)
    if info.get("title"):
        _cache_url_title(url, info["title"])


def _get_cached_ytdlp_info(url: str) -> dict | None:
    now = time.monotonic()
    with _META_CACHE_LOCK:
        entry = _YTDLP_INFO_CACHE.get(url)
        if entry and (now - entry[0]) < _META_CACHE_TTL:
            return entry[1]
        if entry:
            _YTDLP_INFO_CACHE.pop(url, None)
    return None


def _is_user_authorized(user_id: int | str | None) -> bool:
    if user_id is None:
        return not (os.environ.get("ALLOWED_USERS", allowed_users) or "").strip()
    env_allowed = os.environ.get("ALLOWED_USERS")
    effective = env_allowed if env_allowed is not None else allowed_users
    return is_telegram_user_allowed(user_id, allowed_users_env=effective)


def save_summary(summary_data):
    """Persist a summary when MongoDB is configured, without affecting delivery."""
    if summary_collection is None:
        return
    if _summary_repo._collection is not summary_collection:
        SummaryRepository(collection=summary_collection).save(summary_data)
    else:
        _summary_repo.save(summary_data)


def send_to_discord(content):
    """發送訊息到 Discord Webhook；過長時自動上傳為 txt 檔案。"""
    if not enable_discord_webhook:
        logger.debug("Discord Webhook is disabled by configuration.")
        return
    if not discord_webhook_url:
        logger.debug("Discord Webhook URL is not set.")
        return

    try:
        max_length = 1900
        if len(content) <= max_length:
            response = requests.post(
                discord_webhook_url,
                json={"content": content},
                timeout=WEB_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return

        with tempfile.TemporaryDirectory(prefix="discord_") as tmp_dir:
            temp_file_path = os.path.join(tmp_dir, "summary.txt")
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(content)
            with open(temp_file_path, "rb") as f:
                files = {"file": ("summary.txt", f, "text/plain")}
                data = {"content": "📄 摘要內容過長，已上傳為文件"}
                response = requests.post(
                    discord_webhook_url,
                    data=data,
                    files=files,
                    timeout=WEB_REQUEST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
    except Exception as e:
        logger.warning("Failed to send message to Discord: %s", e)


def send_summary_via_email(summary, recipient_email, subject="摘要結果"):
    """發送摘要至設定郵箱（先跳脫 HTML 標籤防止來源網頁標籤注入）。"""
    if not enable_email:
        logger.debug("Email sending is disabled by configuration.")
        return

    try:
        if not smtp_server or not smtp_user or not smtp_password:
            logger.warning("郵件設定不完整，無法發送郵件")
            return

        message = MIMEMultipart()
        message["From"] = smtp_user
        message["To"] = recipient_email

        clean_cc = [addr.strip() for addr in smtp_cc_emails if addr and addr.strip()]
        if clean_cc:
            message["CC"] = ", ".join(clean_cc)
            all_recipients = [recipient_email] + clean_cc
        else:
            all_recipients = [recipient_email]

        safe_subject = sanitize_raw_title(subject, max_length=200) or "摘要結果"
        message["Subject"] = safe_subject

        safe_summary = html.escape(summary or "", quote=False)
        html_summary = markdown.markdown(safe_summary, extensions=["nl2br"])
        message.attach(MIMEText(html_summary, "html", "utf-8"))

        with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=WEB_REQUEST_TIMEOUT_SECONDS) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, all_recipients, message.as_string())
    except Exception as e:
        logger.warning("Failed to send email: %s", e)


def scrape_text_from_url(url):
    """SSRF-safe web page scraping using safe_http_get + trafilatura.extract."""
    try:
        if not is_safe_url(url):
            return [], "不支援或受保護的私有/內部網路網址 (Blocked private or invalid URL)。"
        resp = safe_http_get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            },
            timeout=WEB_REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code >= 400 or not resp.text:
            return [], "無法下載該網頁的內容。"

        raw_html = resp.text
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(raw_html, "lxml")
            if soup.title and soup.title.string and soup.title.string.strip():
                _cache_url_title(url, soup.title.string.strip())
        except Exception:
            pass

        import trafilatura

        text = trafilatura.extract(raw_html, include_formatting=True)
        if text is None or text.strip() == "":
            return [], "提取的內容為空，可能該網站不支持解析。"

        article_content = [chunk.strip() for chunk in text.split("\n") if chunk.strip()]
        if not article_content:
            return [], "提取的內容為空。"
        return article_content, None
    except ValueError as ve:
        return [], str(ve)
    except Exception as e:
        logger.warning("Error scraping URL %s: %s", url, e)
        return [], f"抓取過程中發生錯誤：{str(e)}"


def call_gpt_api(prompt, additional_messages=None, use_llm2_model=False, selected_model=None):
    """呼叫 LLM API，支援多級容錯自動切換 (Multi-tier LLM Fallback)。"""
    return call_llm_with_fallback(
        prompt=prompt,
        additional_messages=additional_messages or [],
        use_llm2_model=use_llm2_model,
        selected_model=selected_model,
        timeout=LLM_TIMEOUT_SECONDS,
    )


def summarize(text_array, language="zh-TW", selected_model=None, raw_title=None, return_title=False, user_note=None):
    """委託至共用 app.services.summarization.summarize，確保 Bot 與 API 行為完全一致。"""
    return _service_summarize(
        text_array,
        selected_model=selected_model,
        language=language,
        raw_title=raw_title,
        return_title=return_title,
        user_note=user_note,
        gpt_caller=call_gpt_api,
    )


def get_ytdlp_cookie_opts(tmp_dir: str | None = None) -> dict:
    """Determine cookie options for yt-dlp using an isolated per-invocation temp copy."""
    chrome_profile = "/chrome-data/.config/google-chrome"
    if os.path.isdir(chrome_profile):
        return {"cookiesfrombrowser": ("chrome", chrome_profile, None, None)}

    for candidate in ("/app/cookies.txt", "cookies.txt", "/cookies.txt"):
        if os.path.isfile(candidate) and os.path.getsize(candidate) > 10:
            target_dir = tmp_dir or tempfile.gettempdir()
            tmp_cookie = os.path.join(target_dir, f"ytdlp_cookies_{uuid.uuid4().hex}.txt")
            try:
                shutil.copyfile(candidate, tmp_cookie)
                os.chmod(tmp_cookie, 0o600)
                return {"cookiefile": tmp_cookie}
            except Exception:
                return {"cookiefile": candidate}
    return {}


def _build_ytdlp_opts(tmp_dir: str | None = None, **overrides) -> dict:
    opts = {
        "extractor_args": {"youtube": {"player_client": ["default,-web_safari"]}},
        "force_ipv4": True,
        "geo_bypass": True,
        "noplaylist": True,
        "socket_timeout": MEDIA_DOWNLOAD_TIMEOUT_SECONDS,
        **get_ytdlp_cookie_opts(tmp_dir=tmp_dir),
    }
    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    if ffmpeg_bin:
        opts["ffmpeg_location"] = ffmpeg_bin
    if ffprobe_bin:
        opts["ffprobe_location"] = ffprobe_bin
    opts.update(overrides)
    return opts


def _cleanup_temp_cookie(ydl_opts: dict, tmp_dir: str | None = None) -> None:
    cookiefile = ydl_opts.get("cookiefile")
    if cookiefile and tmp_dir is None and cookiefile.startswith(tempfile.gettempdir()) and os.path.exists(cookiefile):
        try:
            os.remove(cookiefile)
        except OSError:
            pass


def is_supported_by_ytdlp(url):
    """檢測 URL 是否被 yt-dlp 支援的影片網站，並快取 metadata 供後續步驟複用。"""
    if not is_safe_url(url):
        return False

    unsupported_reason = get_unsupported_media_url_reason(url)
    if unsupported_reason:
        logger.warning(
            "yt-dlp probe skipped for unsupported collection/page URL %s: %s",
            url,
            unsupported_reason.replace("\n", " | "),
        )
        return False

    video_site_patterns = [
        r"youtube\.com|youtu\.be",
        r"vimeo\.com",
        r"bilibili\.com",
        r"dailymotion\.com",
        r"tiktok\.com",
        r"twitch\.tv",
        r"facebook\.com/watch|fb\.watch",
        r"instagram\.com/(p|reel|tv)",
        r"twitter\.com/.*/status|x\.com/.*/status",
        r"soundcloud\.com",
        r"spotify\.com",
        r"bandcamp\.com",
        r"ted\.com/talks",
        r"coursera\.org",
        r"khanacademy\.org",
        r"archive\.org",
        r"pocketcasts\.com|pca\.st",
        r"player\.soundon\.fm",
        r"podcasts\.apple\.com",
    ]
    url_lower = url.lower()
    if not any(re.search(pattern, url_lower) for pattern in video_site_patterns):
        return False

    cached_info = _get_cached_ytdlp_info(url)
    if cached_info is not None:
        info = cached_info
    else:
        with tempfile.TemporaryDirectory(prefix="yt_probe_") as tmp_dir:
            ydl_opts = _build_ytdlp_opts(
                tmp_dir=tmp_dir,
                quiet=True,
                no_warnings=True,
                extract_flat="in_playlist",
                socket_timeout=min(MEDIA_DOWNLOAD_TIMEOUT_SECONDS, YTDLP_PROBE_TIMEOUT_SECONDS),
            )
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                if info:
                    _cache_ytdlp_info(url, info)
            except Exception as e:
                logger.debug("yt-dlp validation error for %s: %s", url, e)
                return True

    if info:
        if info.get("_type") in ("playlist", "multi_video") or ("entries" in info and not info.get("formats")):
            logger.warning("yt-dlp resolved %s to a playlist/channel collection; refusing batch probe.", url)
            return False
        video_indicators = ("formats", "duration", "view_count", "like_count", "upload_date", "uploader")
        if info.get("formats") or info.get("duration", 0) > 0 or any(k in info for k in video_indicators):
            return True
    return False


def clean_subtitle(subtitle_content):
    subtitle_content = re.sub(r"WEBVTT\n\n", "", subtitle_content)
    subtitle_content = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*\n", "", subtitle_content)
    subtitle_content = re.sub(r"\n+", "\n", subtitle_content)
    subtitle_content = re.sub(r"^\d+\n", "", subtitle_content, flags=re.MULTILINE)
    return subtitle_content.strip()


def extract_video_transcript(video_url):
    """提取影片字幕（含 SSRF 檢查與隔離暫存目錄）。"""
    if not is_safe_url(video_url):
        return "unsafe_url"
    if get_unsupported_media_url_reason(video_url):
        return "error"

    with tempfile.TemporaryDirectory(prefix="subs_") as tmp_dir:
        ydl_opts = _build_ytdlp_opts(
            tmp_dir=tmp_dir,
            writesubtitles=True,
            writeautomaticsub=True,
            skip_download=True,
            subtitleslangs=PREFERRED_SUBTITLE_LANGS,
            outtmpl=os.path.join(tmp_dir, "%(id)s.%(ext)s"),
        )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = _get_cached_ytdlp_info(video_url) or ydl.extract_info(video_url, download=False)
                if info:
                    _cache_ytdlp_info(video_url, info)
                video_id = info["id"]

                if "subtitles" in info or "automatic_captions" in info:
                    ydl.download([video_url])
                    subtitle_content = None
                    for sub_lang in PREFERRED_SUBTITLE_LANGS:
                        subtitle_file = os.path.join(tmp_dir, f"{video_id}.{sub_lang}.vtt")
                        if os.path.exists(subtitle_file):
                            with open(subtitle_file, "r", encoding="utf-8") as file:
                                subtitle_content = file.read()
                            break
                    if subtitle_content:
                        return clean_subtitle(subtitle_content)
                    return "no transcript"
                return "no transcript"
        except Exception as e:
            logger.warning("Error extracting video transcript for %s: %s", video_url, e)
            return "error"


def audio_transcription(video_url):
    """下載影片音訊並使用統一 Groq Whisper ASR 管線轉錄（修復 chunk_size 遮蔽與平行安全）。"""
    if not is_safe_url(video_url):
        return ["不支援或受保護的私有/內部網路網址。"]
    unsupported_reason = get_unsupported_media_url_reason(video_url)
    if unsupported_reason:
        return [unsupported_reason]
    try:
        with tempfile.TemporaryDirectory(prefix="yt_audio_") as tmp_dir:
            ydl_opts = _build_ytdlp_opts(
                tmp_dir=tmp_dir,
                format=PREFERRED_AUDIO_FORMAT,
                outtmpl=os.path.join(tmp_dir, f"{uuid.uuid4().hex}.%(ext)s"),
                postprocessors=[{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            )
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                if info:
                    _cache_ytdlp_info(video_url, info)
                output_path = ydl.prepare_filename(info)

            mp3_path = os.path.splitext(output_path)[0] + ".mp3"
            transcript = transcribe_local_audio(mp3_path, asr_timeout=ASR_TIMEOUT_SECONDS)
            return split_transcript_lines(transcript, chunk_size=chunk_size)
    except Exception as e:
        logger.warning("Error in audio_transcription: %s", e)
        return ["音頻轉錄失敗。"]


def retrieve_video_transcript_from_url(video_url):
    """通用的影片字幕轉文字函數，含 SSRF 與頻道/清單網址檢查。"""
    if not is_safe_url(video_url):
        return ["不支援或受保護的私有/內部網路網址。"]
    unsupported_reason = get_unsupported_media_url_reason(video_url)
    if unsupported_reason:
        logger.warning(
            "Rejected unsupported media URL in retrieve_video_transcript_from_url (%s): %s",
            video_url,
            unsupported_reason.replace("\n", " | "),
        )
        return [unsupported_reason]
    try:
        subtitle_content = extract_video_transcript(video_url)
        if subtitle_content == "unsafe_url":
            return ["不支援或受保護的私有/內部網路網址。"]
        if subtitle_content == "no transcript":
            if use_audio_fallback:
                return audio_transcription(video_url)
            return ["該影片沒有可用的字幕，且音頻轉換功能未啟用。"]
        if subtitle_content == "error":
            return ["暫時無法轉錄"]

        cleaned_content = re.sub(r"WEBVTT\n\n", "", subtitle_content)
        cleaned_content = re.sub(r"\d+:\d+:\d+\.\d+ --> \d+:\d+:\d+\.\d+\n", "", cleaned_content)
        cleaned_content = re.sub(r"\n\n", " ", cleaned_content)

        output_chunks = []
        current_chunk = ""
        for word in cleaned_content.split():
            if len(current_chunk) + len(word) + 1 <= chunk_size:
                current_chunk += word + " "
            else:
                output_chunks.append(current_chunk.strip())
                current_chunk = word + " "
        if current_chunk:
            output_chunks.append(current_chunk.strip())
        return output_chunks
    except Exception as e:
        logger.warning("Error in retrieve_video_transcript_from_url: %s", e)
        return ["無法獲取字幕或進行音頻轉換。"]


def process_pocketcasts_url(url):
    """處理 Pocket Casts URL，提取指定或最新集數並轉錄。"""
    try:
        if not is_safe_url(url):
            return ["不支援或受保護的私有/內部網路網址。"]

        episode_info = extract_pocketcasts_episode(url)
        if episode_info and episode_info.get("audio_url"):
            ep_title = (episode_info.get("episode_title") or "").strip()
            pod_title = (episode_info.get("podcast_title") or "").strip()
            if ep_title and pod_title and pod_title not in ep_title:
                _cache_url_title(url, f"{ep_title} - {pod_title}")
            elif ep_title or pod_title:
                _cache_url_title(url, ep_title or pod_title)
            return download_and_transcribe_podcast(episode_info["audio_url"])

        rss_url = extract_rss_from_pocketcasts(url, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if not rss_url:
            return ["無法從 Pocket Casts 提取音訊或 RSS feed。"]

        episodes = get_latest_podcast_episode(rss_url, max_episodes=1, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if not episodes:
            return ["無法從 RSS feed 獲取 podcast episodes。"]

        _cache_url_title(url, episodes[0].get("title"))
        return download_and_transcribe_podcast(episodes[0]["audio_url"])
    except Exception as e:
        logger.warning("Error processing Pocket Casts URL: %s", e)
        return ["處理 Pocket Casts URL 時發生錯誤。"]


def process_soundon_url(url):
    """處理 SoundOn URL，提取並轉錄最新 podcast episode。"""
    try:
        if not is_safe_url(url):
            return ["不支援或受保護的私有/內部網路網址。"]
        rss_url = extract_rss_from_soundon(url, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if not rss_url:
            return ["無法從 SoundOn 頁面提取 RSS feed。"]
        episodes = get_latest_podcast_episode(rss_url, max_episodes=1, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if not episodes:
            return ["無法從 RSS feed 獲取 podcast episodes。"]
        _cache_url_title(url, episodes[0].get("title"))
        return download_and_transcribe_podcast(episodes[0]["audio_url"])
    except Exception as e:
        logger.warning("Error processing SoundOn URL: %s", e)
        return ["處理 SoundOn URL 時發生錯誤。"]


def process_apple_podcast_url(url):
    """處理 Apple Podcast URL，優先精準提取指定單集 (?i=...) 或最新 podcast episode。"""
    try:
        if not is_safe_url(url):
            return ["不支援或受保護的私有/內部網路網址。"]
        info = extract_episode_from_apple_podcast(url, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if info and info.get("episode"):
            ep = info["episode"]
            _cache_url_title(url, ep.get("title"))
            return download_and_transcribe_podcast(ep["audio_url"])
        if info and info.get("target_episode_id"):
            return ["無法在 Apple Podcast 找到指定的單集音訊。"]
        rss_url = (info or {}).get("rss_url") or extract_rss_from_apple_podcast(url, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if not rss_url:
            return ["無法從 Apple Podcast 提取 RSS feed。"]
        episodes = get_latest_podcast_episode(rss_url, max_episodes=1, timeout=int(WEB_REQUEST_TIMEOUT_SECONDS))
        if not episodes:
            return ["無法從 RSS feed 獲取 podcast episodes。"]
        _cache_url_title(url, episodes[0].get("title"))
        return download_and_transcribe_podcast(episodes[0]["audio_url"])
    except Exception as e:
        logger.warning("Error processing Apple Podcast URL: %s", e)
        return ["處理 Apple Podcast URL 時發生錯誤。"]


def download_video_audio(url):
    """Download and convert audio synchronously; callers must offload and delete the returned file."""
    if not is_safe_url(url):
        raise ValueError("Unsafe or invalid URL provided.")
    unsupported_reason = get_unsupported_media_url_reason(url)
    if unsupported_reason:
        logger.warning(
            "Rejected unsupported media URL in download_video_audio (%s): %s",
            url,
            unsupported_reason.replace("\n", " | "),
        )
        raise ValueError(unsupported_reason)
    temp_uuid = str(uuid.uuid4())
    tmp_base = os.path.join(tempfile.gettempdir(), temp_uuid)
    ydl_opts = _build_ytdlp_opts(
        format=PREFERRED_AUDIO_FORMAT,
        outtmpl=f"{tmp_base}.%(ext)s",
        postprocessors=[{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    )
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)
    except Exception:
        for leftover in glob.glob(f"{tmp_base}.*"):
            try:
                os.remove(leftover)
            except OSError:
                pass
        raise
    finally:
        _cleanup_temp_cookie(ydl_opts)
    return f"{tmp_base}.mp3"


def get_video_title(video_url, localize=True):
    """使用 yt-dlp 提取影片標題（複用快取避免重複探測）。"""
    if not is_safe_url(video_url):
        return "影片"
    if get_unsupported_media_url_reason(video_url):
        return "不支援的頻道或清單網址"
    cached_info = _get_cached_ytdlp_info(video_url)
    if cached_info and cached_info.get("title"):
        raw_title = cached_info["title"]
        return localize_title(raw_title) if localize else raw_title
    try:
        with tempfile.TemporaryDirectory(prefix="yt_title_") as tmp_dir:
            ydl_opts = _build_ytdlp_opts(
                tmp_dir=tmp_dir,
                quiet=True,
                no_warnings=True,
                extract_flat="in_playlist",
                socket_timeout=min(MEDIA_DOWNLOAD_TIMEOUT_SECONDS, YTDLP_PROBE_TIMEOUT_SECONDS),
            )
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                if info:
                    _cache_ytdlp_info(video_url, info)
                raw_title = (info or {}).get("title", "影片")
                return localize_title(raw_title) if localize else raw_title
    except Exception as e:
        logger.warning("Error extracting video title: %s", e)
        return "影片"


def get_web_title(user_input, localize=True):
    """提取 URL 標題（含 SSRF 檢查與單次請求快取複用）。"""
    if not is_safe_url(user_input):
        return "不支援或受保護的私有/內部網路網址。"
    if get_unsupported_media_url_reason(user_input):
        return "不支援的頻道或清單網址"

    cached = _get_cached_title(user_input)
    if cached:
        return localize_title(cached) if localize else cached

    if is_pocketcasts_url(user_input):
        podcast_title = get_pocketcasts_title(user_input)
        if podcast_title:
            _cache_url_title(user_input, podcast_title)
            return localize_title(podcast_title) if localize else podcast_title

    if is_supported_by_ytdlp(user_input):
        return get_video_title(user_input, localize=localize)

    try:
        resp = safe_http_get(
            user_input,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                )
            },
            timeout=WEB_REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code >= 400 or not resp.text:
            return "無法下載該網頁的內容。"
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "lxml")
        title = soup.title.string.strip() if soup.title and soup.title.string else "無法提取標題"
        _cache_url_title(user_input, title)
        return localize_title(title) if localize else title
    except Exception as e:
        logger.warning("Error fetching title for %s: %s", user_input, e)
        return "抓取過程中發生錯誤。"


def process_user_input(user_input):
    """處理用戶輸入的文字或網址，並返回適當的文本內容數組。"""
    if isinstance(user_input, str) and re.match(r"www\.\S+", user_input.strip(), re.IGNORECASE):
        user_input = f"https://{user_input.strip()}"
    url_pattern = re.compile(r"https?://", re.IGNORECASE)
    if url_pattern.match(user_input):
        if not is_safe_url(user_input):
            logger.warning("Blocked unsafe/internal URL: %s", user_input)
            return [], "不支援或受保護的私有/內部網路網址 (Blocked private or invalid URL)。"
        unsupported_reason = get_unsupported_media_url_reason(user_input)
        if unsupported_reason:
            logger.warning(
                "Rejected unsupported collection/page URL %s: %s",
                user_input,
                unsupported_reason.replace("\n", " | "),
            )
            return [], unsupported_reason
        if is_pocketcasts_url(user_input):
            return process_pocketcasts_url(user_input)
        if is_soundon_url(user_input):
            return process_soundon_url(user_input)
        if is_apple_podcast_url(user_input):
            return process_apple_podcast_url(user_input)
        if is_supported_by_ytdlp(user_input):
            return retrieve_video_transcript_from_url(user_input)
        text_array, error = scrape_text_from_url(user_input)
        if error:
            return [], error
        return text_array
    return split_user_input(user_input)


async def _reply_or_edit(bot, chat_id, processing_message, text, **kwargs):
    """Safely edit processing_message if present, otherwise send a new message (handles SHOW_PROCESSING=0)."""
    if processing_message is not None:
        return await bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_message.message_id,
            text=text,
            **kwargs,
        )
    return await bot.send_message(chat_id=chat_id, text=text, **kwargs)


async def _delete_msg(bot, chat_id, msg):
    if msg is not None:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        except Exception:
            pass


def _get_chat_state(context) -> dict:
    """Return chat-scoped state store (context.chat_data) when available so histories never leak across chats."""
    chat_data = getattr(context, "chat_data", None)
    if isinstance(chat_data, dict):
        return chat_data
    return context.user_data


def _evict_expired_chat_items(
    chat_state: dict,
    prefix: str,
    ttl: float = _AD_HIDDEN_TTL_SECONDS,
    max_items: int = _MAX_AD_HIDDEN_ITEMS,
) -> None:
    """Evict expired or excess transient entries with the given prefix from chat_state."""
    now = time.time()
    keys = [k for k in chat_state if k.startswith(prefix)]
    for k in keys:
        val = chat_state.get(k)
        if isinstance(val, dict) and (now - float(val.get("created_at", now))) > ttl:
            chat_state.pop(k, None)
    remaining = [k for k in chat_state if k.startswith(prefix)]
    if len(remaining) > max_items:
        remaining.sort(key=lambda k: float(chat_state[k].get("created_at", 0.0)) if isinstance(chat_state.get(k), dict) else 0.0)
        for k in remaining[: len(remaining) - max_items]:
            chat_state.pop(k, None)


def _evict_expired_ad_hidden(chat_state: dict) -> None:
    _evict_expired_chat_items(chat_state, "ad_hidden_")


def _preflight_check_urls(urls: list[str]) -> tuple[list[str], list[dict]]:
    """Run SSRF and channel/playlist validation on candidate URLs before processing."""
    valid_urls: list[str] = []
    rejected_items: list[dict] = []
    for url in urls:
        if not is_safe_url(url):
            reason = "不支援或受保護的私有/內部網路網址 (Blocked private or invalid URL)。"
            info = classify_extraction_failure(url, reason)
            rejected_items.append({"url": url, "reason": reason, "suggestion": info["suggestion"], "code": info["code"]})
            continue
        unsupported_reason = get_unsupported_media_url_reason(url)
        if unsupported_reason:
            info = classify_extraction_failure(url, unsupported_reason)
            rejected_items.append({"url": url, "reason": unsupported_reason, "suggestion": info["suggestion"], "code": info["code"]})
            continue
        valid_urls.append(url)
    return valid_urls, rejected_items


def _build_url_recovery_reply(
    chat_state: dict,
    url: str,
    error_msg: str,
    user_note: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Build diagnostic failure message with suggestions and interactive recovery buttons."""
    _evict_expired_chat_items(chat_state, "url_retry_")
    info = classify_extraction_failure(url, error_msg)
    retry_id = str(uuid.uuid4())[:8]
    chat_state[f"url_retry_{retry_id}"] = {
        "url": url,
        "user_note": user_note,
        "status": "pending",
        "created_at": time.time(),
    }

    lines = [
        error_msg.strip() or "⚠️ 無法取得該連結的內容。",
        "",
        f"💡 <b>建議處理方式：</b>{html.escape(info['suggestion'])}",
    ]
    if "排查代碼：" not in (error_msg or ""):
        lines.append(f"🔎 <code>排查代碼：{html.escape(info['code'])}</code>")
    lines.append("\n請問您希望如何處理？")

    buttons: list[list[InlineKeyboardButton]] = []
    if info.get("can_force_audio"):
        buttons.append([InlineKeyboardButton("🎙️ 改用 Whisper 音訊轉錄並摘要", callback_data=f"url_act:{retry_id}:force_audio")])
    if info.get("retryable"):
        buttons.append([InlineKeyboardButton("🔄 重新嘗試抓取", callback_data=f"url_act:{retry_id}:retry")])
    if user_note:
        buttons.append([InlineKeyboardButton("💬 改為僅就我的文字與 AI 討論", callback_data=f"url_act:{retry_id}:chat_note")])
    buttons.append([InlineKeyboardButton("❌ 略過 / 取消", callback_data=f"url_act:{retry_id}:cancel")])

    return "\n".join(lines), InlineKeyboardMarkup(buttons)


def _build_batch_intent_card(
    valid_urls: list[str],
    rejected_items: list[dict],
    dropped_count: int,
    user_note: str | None,
    batch_id: str,
) -> tuple[str, InlineKeyboardMarkup]:
    """Render an interactive intent-confirmation card for multi-URL inputs."""
    lines = [f"📋 <b>偵測到多個連結</b>（可處理 <b>{len(valid_urls)}</b> 筆）："]
    for idx, url in enumerate(valid_urls, 1):
        display_url = url if len(url) <= 75 else f"{url[:72]}..."
        lines.append(f"{idx}. <code>{html.escape(display_url)}</code>")

    if dropped_count > 0:
        lines.append(f"⚠️ <i>為避免阻塞資源，其餘 {dropped_count} 筆超出單次上限（10 筆）已略過。</i>")

    if rejected_items:
        lines.append(f"\n🚫 <b>預檢略過 {len(rejected_items)} 筆不支援／受保護連結：</b>")
        for item in rejected_items:
            short_u = item["url"] if len(item["url"]) <= 60 else f"{item['url'][:57]}..."
            lines.append(
                f"• <code>{html.escape(short_u)}</code>\n"
                f"  原因：<code>{html.escape(item['code'])}</code> — {html.escape(item['suggestion'])}"
            )

    if user_note:
        preview = user_note if len(user_note) <= 120 else f"{user_note[:117]}..."
        lines.append(f"\n📝 <b>附帶備註／提問：</b><blockquote>{html.escape(preview)}</blockquote>")
        lines.append("<i>（選擇「個別逐篇處理」時會套用至每一篇；選擇「整合／比較」時會針對所有來源一同回應）</i>")

    lines.append("\n請問您希望如何處理這批連結？")

    n = len(valid_urls)
    if n == 1:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ 繼續處理這 1 筆有效連結", callback_data=f"batch:{batch_id}:individual")],
            [InlineKeyboardButton("📄 僅轉逐字稿 (.txt)", callback_data=f"batch:{batch_id}:transcript")],
            [InlineKeyboardButton("❌ 取消", callback_data=f"batch:{batch_id}:cancel")],
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📑 個別逐篇處理（{n} 篇）", callback_data=f"batch:{batch_id}:individual")],
            [
                InlineKeyboardButton("🧩 整合成單篇綜合重點", callback_data=f"batch:{batch_id}:digest"),
                InlineKeyboardButton("⚖️ 跨來源比較差異", callback_data=f"batch:{batch_id}:compare"),
            ],
            [
                InlineKeyboardButton("📄 僅批次轉逐字稿 (.txt)", callback_data=f"batch:{batch_id}:transcript"),
                InlineKeyboardButton("❌ 取消", callback_data=f"batch:{batch_id}:cancel"),
            ],
        ])
    return "\n".join(lines), keyboard


def _fetch_boa_answer() -> str:
    response = requests.get(ANSWER_BOOK_API, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("answer", "無法取得回答")


def _build_apikey_status_keyboard(has_key: bool) -> InlineKeyboardMarkup:
    if not has_key:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 產生我的 API Key", callback_data="apikey:create")],
            [InlineKeyboardButton("📖 查看 cURL 用法", callback_data="apikey:curl")],
        ])
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Rotate 輪換金鑰", callback_data="apikey:rotate_confirm"),
            InlineKeyboardButton("🗑️ 撤銷金鑰", callback_data="apikey:revoke_confirm"),
        ],
        [InlineKeyboardButton("📖 查看 cURL 用法", callback_data="apikey:curl")],
    ])


def _format_issued_apikey_html(result: dict, base_url: str, is_rotated: bool) -> str:
    api_key_escaped = html.escape(result["api_key"])
    curl_guide_escaped = html.escape(build_curl_usage_guide(base_url, api_key=result["api_key"]))
    base_url_escaped = html.escape(base_url)
    title = "🔄 <b>API Key 輪換成功（舊金鑰已立即失效）</b>" if is_rotated else "🔑 <b>API Key 產生成功</b>"
    return (
        f"{title}\n\n"
        "⚠️ <b>基於安全考量，完整金鑰僅顯示這一次，請立即妥善保存：</b>\n"
        f"<pre><code>{api_key_escaped}</code></pre>\n\n"
        f"🌐 <b>API 端點：</b><code>{base_url_escaped}</code>\n\n"
        "📖 <b>完整 cURL 使用教學（可直接複製執行）：</b>\n"
        f"<pre><code>{curl_guide_escaped}</code></pre>"
    )


async def _finalize_and_deliver_summary(
    *,
    bot,
    chat_id: int,
    user_id: int | None,
    user_data: dict,
    chat_state: dict | None = None,
    status_msg,
    text_array: list[str],
    original_url: str | None,
    raw_title: str | None,
    user_note: str | None,
    default_title: str,
    source_label: str,
    discord_prefix: str,
    send_email: bool = True,
    summary_override: tuple[str, str | None] | None = None,
) -> None:
    target_chat_state = chat_state if chat_state is not None else user_data
    language = user_data.get("language", "zh-TW")
    selected_model = user_data.get("selected_model", None)

    summary, ai_title = summary_override if summary_override is not None else await run_blocking(
        summarize,
        text_array,
        language=language,
        selected_model=selected_model,
        raw_title=raw_title,
        return_title=True,
        user_note=user_note,
    )
    if is_summary_error_message(summary):
        await _delete_msg(bot, chat_id, status_msg)
        await bot.send_message(chat_id=chat_id, text=summary or "⚠️ 摘要生成失敗，請稍後再試。")
        return

    title = resolve_final_title(ai_title, raw_title, language, default_title)
    summary_with_original = compose_summary_with_source(
        title,
        summary,
        original_url=original_url,
        raw_title=raw_title,
        user_note=user_note,
    )

    target_chat_state["conversation_history"] = {
        "title": title,
        "raw_title": raw_title,
        "user_note": user_note,
        "original_content": text_array,
        "summary": summary,
        "source_url": original_url or source_label,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "messages": [],
        "language": language,
    }

    if send_email and enable_email and smtp_user:
        await run_blocking(send_summary_via_email, summary_with_original, smtp_user, subject=title)

    summary_data = {
        "telegram_id": user_id,
        "url": original_url,
        "title": title,
        "original_title": raw_title,
        "user_note": user_note,
        "summary": summary_with_original,
        "original_content": text_array,
        "language": language,
        "timestamp": datetime.now(),
    }
    await run_blocking(save_summary, summary_data)

    await _delete_msg(bot, chat_id, status_msg)

    if enable_discord_webhook:
        discord_message = f"{discord_prefix}\n{summary_with_original}"
        await run_blocking(send_to_discord, discord_message)

    await _send_telegram_formatted(
        bot,
        chat_id,
        summary_with_original,
        reply_markup=get_summary_quick_reply_keyboard(),
    )


async def _deliver_extracted_or_ad_hidden(
    *,
    bot,
    chat_id: int,
    user_id: int | None,
    user_data: dict,
    chat_state: dict,
    status_msg,
    text_array: list[str],
    source_input: str,
    user_note: str | None,
    default_title: str,
    raw_title: str | None = None,
    source_label: str = "text input",
) -> None:
    """Run Clef ad decision check (when enabled) and deliver summary or ad-hidden card."""
    user_ad_pref = user_data.get("ad_filter", None)
    is_url_input = is_url(source_input)
    if is_decision_ad_filter_enabled(user_ad_pref):
        is_ad, _decision_data = await run_blocking(
            is_advertisement_content,
            text_array,
            url=source_input if is_url_input else None,
            mongo_collection=decision_collection,
            timeout=CLEF_TIMEOUT_SECONDS,
        )
        if is_ad:
            await _delete_msg(bot, chat_id, status_msg)
            _evict_expired_ad_hidden(chat_state)
            submission_id = str(uuid.uuid4())[:8]
            chat_state[f"ad_hidden_{submission_id}"] = {
                "text_array": text_array,
                "user_input": source_input,
                "user_note": user_note,
                "created_at": time.time(),
            }
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("👁️ 仍要查看摘要", callback_data=f"show_ad:{submission_id}")]
            ])
            title_hint = ""
            if is_url_input:
                t = raw_title or await run_blocking(get_web_title, source_input)
                if is_valid_raw_title(t):
                    title_hint = f"📌 {html.escape(t)}\n\n"
            ad_msg = (
                f"{title_hint}"
                "🚫 <b>【廣告內容已自動隱藏】</b>\n\n"
                "經 Clef 決策模型判定，此內容包含高度商業宣傳、廣告行銷或垃圾訊息，已自動隱藏。\n\n"
                "💡 若您仍需要對此內容生成摘要，可點擊下方按鈕強制查看。"
            )
            await bot.send_message(
                chat_id=chat_id,
                text=ad_msg,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return

    original_url = source_input if is_url_input else None
    resolved_raw_title = raw_title
    if is_url_input and resolved_raw_title is None:
        resolved_raw_title = await run_blocking(get_web_title, source_input, False)

    await _finalize_and_deliver_summary(
        bot=bot,
        chat_id=chat_id,
        user_id=user_id,
        user_data=user_data,
        chat_state=chat_state,
        status_msg=status_msg,
        text_array=text_array,
        original_url=original_url,
        raw_title=resolved_raw_title,
        user_note=user_note,
        default_title=default_title,
        source_label=source_label,
        discord_prefix="🔔 新的摘要已生成：",
    )


async def _extract_url_for_batch(url: str) -> tuple[list[str] | None, str | None, str | None]:
    """Extract content and title for a single URL within a batch with wall-clock timeout."""
    try:
        raw_res = await asyncio.wait_for(
            run_blocking(process_user_input, url),
            timeout=URL_PROCESSING_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return (
            None,
            None,
            f"⏱️ 網址處理逾時（超過 {int(URL_PROCESSING_TIMEOUT_SECONDS)} 秒未完成）。\n排查代碼：URL_PROCESSING_TIMEOUT",
        )
    except Exception as exc:
        logger.warning("Batch extraction error for %s: %s", url, exc, exc_info=True)
        return None, None, f"⚠️ 擷取過程發生錯誤：{exc}"

    if isinstance(raw_res, tuple):
        if len(raw_res) == 2 and not raw_res[0]:
            return None, None, str(raw_res[1])
        text_array = raw_res[0]
    else:
        text_array = raw_res

    if is_extraction_error(text_array):
        return None, None, text_array[0]
    if not text_array:
        return None, None, "⚠️ 未能從該連結擷取到任何有效內容。"

    raw_title = await run_blocking(get_web_title, url, False)
    return text_array, raw_title, None


async def _execute_batch_individual(
    *,
    bot,
    chat_id: int,
    user_id: int | None,
    user_data: dict,
    chat_state: dict,
    status_msg,
    batch_id: str,
    saved: dict,
    urls_to_run: list[str],
) -> None:
    language = user_data.get("language", "zh-TW")
    default_title = "Text Summary" if language == "en" else "短文之摘要"
    user_note = saved.get("user_note")
    total = len(urls_to_run)
    succeeded = 0
    failed_items: list[dict] = []

    for idx, url in enumerate(urls_to_run, 1):
        short_u = url if len(url) <= 65 else f"{url[:62]}..."
        try:
            await _reply_or_edit(
                bot,
                chat_id,
                status_msg,
                f"⏳ 正在個別處理（{idx}/{total}）：\n{short_u}",
            )
        except Exception:
            pass

        text_array, raw_title, err_msg = await _extract_url_for_batch(url)
        if err_msg or not text_array:
            info = classify_extraction_failure(url, err_msg)
            failed_items.append({"url": url, "error": err_msg or "無法擷取內容", "code": info["code"], "suggestion": info["suggestion"]})
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ <b>第 {idx}/{total} 筆失敗</b>：<code>{html.escape(short_u)}</code>\n"
                    f"原因：{html.escape(err_msg or '無法擷取內容')}\n"
                    f"💡 建議：{html.escape(info['suggestion'])}"
                ),
                parse_mode="HTML",
            )
            continue

        await _deliver_extracted_or_ad_hidden(
            bot=bot,
            chat_id=chat_id,
            user_id=user_id,
            user_data=user_data,
            chat_state=chat_state,
            status_msg=None,
            text_array=text_array,
            source_input=url,
            user_note=user_note,
            default_title=default_title,
            raw_title=raw_title,
        )
        succeeded += 1

    if failed_items:
        saved["failed_urls"] = [item["url"] for item in failed_items]
        saved["status"] = "partial_failed"
        retry_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🔄 僅重試失敗的 {len(failed_items)} 筆", callback_data=f"batch:{batch_id}:retry_individual")],
            [InlineKeyboardButton("❌ 結束", callback_data=f"batch:{batch_id}:cancel")],
        ])
        await _reply_or_edit(
            bot,
            chat_id,
            status_msg,
            f"⚠️ 批次個別處理完成：成功 {succeeded} 筆，失敗 {len(failed_items)} 筆。請問是否重試失敗項目？",
            reply_markup=retry_kb,
        )
    else:
        chat_state.pop(f"batch_intent_{batch_id}", None)
        await _reply_or_edit(bot, chat_id, status_msg, f"✅ 批次個別處理完成：全部 {succeeded} 筆已輸出！")


async def _execute_batch_synthesis(
    *,
    bot,
    chat_id: int,
    user_id: int | None,
    user_data: dict,
    chat_state: dict,
    status_msg,
    batch_id: str,
    saved: dict,
    mode: str,
    urls_to_extract: list[str],
) -> None:
    sources: list[dict] = list(saved.get("sources") or [])
    failed_items: list[dict] = []
    total = len(urls_to_extract)
    mode_label = "跨來源比較分析" if mode == "compare" else "單篇綜合重點"

    for idx, url in enumerate(urls_to_extract, 1):
        short_u = url if len(url) <= 65 else f"{url[:62]}..."
        try:
            await _reply_or_edit(
                bot,
                chat_id,
                status_msg,
                f"⏳ 正在擷取內容以準備「{mode_label}」（{idx}/{total}）：\n{short_u}",
            )
        except Exception:
            pass

        text_array, raw_title, err_msg = await _extract_url_for_batch(url)
        if err_msg or not text_array:
            info = classify_extraction_failure(url, err_msg)
            failed_items.append({"url": url, "error": err_msg or "無法擷取內容", "code": info["code"], "suggestion": info["suggestion"]})
        else:
            sources.append({"url": url, "title": raw_title, "text_array": text_array})

    if failed_items:
        saved["sources"] = sources
        saved["failed_urls"] = [item["url"] for item in failed_items]
        saved["status"] = "awaiting_partial_decision"
        lines = [f"⚠️ <b>準備「{mode_label}」時有 {len(failed_items)} 筆擷取失敗</b>（已成功 {len(sources)} 筆）："]
        for item in failed_items:
            short_u = item["url"] if len(item["url"]) <= 60 else f"{item['url'][:57]}..."
            lines.append(
                f"• <code>{html.escape(short_u)}</code>\n"
                f"  原因：<code>{html.escape(item['code'])}</code> — {html.escape(item['suggestion'])}"
            )
        lines.append("\n請問您希望如何繼續？")
        buttons: list[list[InlineKeyboardButton]] = []
        if sources:
            buttons.append([InlineKeyboardButton(f"✅ 僅用成功的 {len(sources)} 筆繼續{mode_label}", callback_data=f"batch:{batch_id}:proceed_{mode}")])
        buttons.append([InlineKeyboardButton(f"🔄 重試失敗的 {len(failed_items)} 筆", callback_data=f"batch:{batch_id}:retry_{mode}")])
        if sources:
            buttons.append([InlineKeyboardButton(f"📑 改為只對成功的 {len(sources)} 筆個別摘要", callback_data=f"batch:{batch_id}:fallback_individual")])
        buttons.append([InlineKeyboardButton("❌ 取消", callback_data=f"batch:{batch_id}:cancel")])
        await _reply_or_edit(bot, chat_id, status_msg, "\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return

    if not sources:
        chat_state.pop(f"batch_intent_{batch_id}", None)
        await _reply_or_edit(bot, chat_id, status_msg, "❌ 所有連結皆未能擷取有效內容，無法整合。")
        return

    await _deliver_batch_synthesis_result(
        bot=bot,
        chat_id=chat_id,
        user_id=user_id,
        user_data=user_data,
        chat_state=chat_state,
        status_msg=status_msg,
        batch_id=batch_id,
        saved=saved,
        mode=mode,
        sources=sources,
    )


async def _deliver_batch_synthesis_result(
    *,
    bot,
    chat_id: int,
    user_id: int | None,
    user_data: dict,
    chat_state: dict,
    status_msg,
    batch_id: str,
    saved: dict,
    mode: str,
    sources: list[dict],
) -> None:
    language = user_data.get("language", "zh-TW")
    selected_model = user_data.get("selected_model", None)
    user_note = saved.get("user_note")
    mode_label = "跨來源比較分析" if mode == "compare" else "單篇綜合重點"
    try:
        await _reply_or_edit(bot, chat_id, status_msg, f"🤖 正在將 {len(sources)} 份來源進行「{mode_label}」中，請稍候...")
    except Exception:
        pass

    summary, ai_title = await run_blocking(
        _service_summarize_batch,
        sources,
        mode=mode,
        language=language,
        selected_model=selected_model,
        user_note=user_note,
        gpt_caller=call_gpt_api,
    )
    if is_summary_error_message(summary):
        await _reply_or_edit(bot, chat_id, status_msg, summary or "⚠️ 跨來源整合生成失敗，請稍後再試。")
        return

    source_list_md = "\n".join(
        f"{idx}. [{sanitize_raw_title(s.get('title') or '', max_length=100) or s['url']}]({s['url']})"
        for idx, s in enumerate(sources, 1)
    )
    summary_with_refs = f"{summary}\n\n---\n\n📚 **整合來源清單（共 {len(sources)} 筆）**\n{source_list_md}"
    combined_raw_chunks = [
        f"[{idx}] {s.get('title') or s['url']}\n" + "\n".join(s.get("text_array") or [])
        for idx, s in enumerate(sources, 1)
    ]
    default_title = f"{mode_label}（{len(sources)} 篇）"

    await _finalize_and_deliver_summary(
        bot=bot,
        chat_id=chat_id,
        user_id=user_id,
        user_data=user_data,
        chat_state=chat_state,
        status_msg=status_msg,
        text_array=combined_raw_chunks,
        original_url=None,
        raw_title=f"{mode_label}（共 {len(sources)} 篇）",
        user_note=user_note,
        default_title=default_title,
        source_label=", ".join(s["url"] for s in sources),
        discord_prefix=f"🔔 新的{mode_label}已生成：",
        summary_override=(summary_with_refs, ai_title),
    )
    chat_state.pop(f"batch_intent_{batch_id}", None)


async def _execute_batch_transcript(
    *,
    bot,
    chat_id: int,
    status_msg,
    batch_id: str,
    chat_state: dict,
    urls_to_run: list[str],
) -> None:
    total = len(urls_to_run)
    succeeded = 0
    failed_count = 0
    for idx, url in enumerate(urls_to_run, 1):
        short_u = url if len(url) <= 65 else f"{url[:62]}..."
        try:
            await _reply_or_edit(bot, chat_id, status_msg, f"⏳ 正在擷取逐字稿／全文（{idx}/{total}）：\n{short_u}")
        except Exception:
            pass
        text_array, raw_title, err_msg = await _extract_url_for_batch(url)
        if err_msg or not text_array:
            failed_count += 1
            info = classify_extraction_failure(url, err_msg)
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    f"❌ <b>第 {idx}/{total} 筆逐字稿失敗</b>：<code>{html.escape(short_u)}</code>\n"
                    f"原因：{html.escape(err_msg or '無法擷取內容')}\n"
                    f"💡 建議：{html.escape(info['suggestion'])}"
                ),
                parse_mode="HTML",
            )
            continue

        content = "\n".join(text_array) + "\n"
        bio = io.BytesIO(content.encode("utf-8"))
        bio.name = f"transcript_{idx}.txt"
        caption = f"📄 [{idx}/{total}] {raw_title or short_u}"
        await bot.send_document(chat_id=chat_id, document=bio, filename=bio.name, caption=caption[:1024])
        succeeded += 1

    chat_state.pop(f"batch_intent_{batch_id}", None)
    await _reply_or_edit(bot, chat_id, status_msg, f"✅ 批次逐字稿輸出完成：成功 {succeeded} 筆，失敗 {failed_count} 筆。")


async def _handle_quick_reply_action(
    *,
    bot,
    chat_id: int,
    user_data: dict,
    chat_state: dict | None = None,
    history: dict,
    action_type: str,
    user_message_text: str | None = None,
    status_msg=None,
) -> None:
    target_chat_state = chat_state if chat_state is not None else user_data
    language = user_data.get("language", "zh-TW")
    selected_model = user_data.get("selected_model", None)
    raw_content = build_quick_reply_source(history)

    if action_type == "image":
        prompt_task = (
            "Based on the following content, generate a concise, high-impact English visual prompt (under 35 words) "
            "for generating a concept art illustration that captures the central essence of this topic. "
            "Only output the visual prompt directly without quotes:\n\n" + raw_content[:2000]
        )
        image_prompt = await run_blocking(
            call_gpt_api,
            prompt_task,
            [{"role": "system", "content": "You are a visual concept prompt designer."}],
            selected_model=selected_model,
        )
        if not isinstance(image_prompt, str) or not image_prompt.strip():
            err_text = "⚠️ AI 模型暫時無回應，請稍後再試。"
            await _reply_or_edit(bot, chat_id, status_msg, err_text, reply_markup=get_summary_quick_reply_keyboard())
            return

        await _delete_msg(bot, chat_id, status_msg)
        clean_prompt = image_prompt.strip().strip('"').strip("'")
        image_url = build_concept_image_url(clean_prompt)
        caption = (
            "🎨 <b>【AI 主題概念圖】</b>\n\n"
            f"💡 <b>視覺概念</b>：<code>{html.escape(clean_prompt)}</code>\n\n"
            "點擊下方按鈕可繼續切換不同摘要視角 👇"
        )
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=get_summary_quick_reply_keyboard(),
        )
        return

    if action_type == "wiki":
        title = history.get("title") or history.get("source_url", "AI 內容深度解析")
        source_url = history.get("source_url")
        original_url = source_url if source_url and is_url(source_url) else None
        content_to_publish = prepare_wiki_content(
            title=title,
            summary=history.get("summary", ""),
            original_url=original_url,
            raw_title=history.get("raw_title"),
            user_note=history.get("user_note"),
        )
        wiki_res = await run_blocking(publish_wiki_page, content_to_publish, title=title)
        if wiki_res.get("success"):
            reply_html = (
                "📚 <b>【David888 Wiki 發布成功】</b>\n\n"
                f"📝 頁面路徑：<code>{html.escape(str(wiki_res.get('path', '')))}</code>\n"
                f"🌐 線上好讀版：{html.escape(str(wiki_res.get('shareUrl', '')))}\n"
                f"🖥️ 2D 簡報模式：{html.escape(str(wiki_res.get('presentUrl', '')))}\n"
                f"📖 電子書模式：{html.escape(str(wiki_res.get('bookUrl', '')))}\n"
                f"🎨 排版主題：<code>{html.escape(str(wiki_res.get('theme', 'tokyo-night')))}</code>"
            )
            await _reply_or_edit(
                bot,
                chat_id,
                status_msg,
                reply_html,
                parse_mode="HTML",
                reply_markup=get_summary_quick_reply_keyboard(),
            )
        else:
            err_reply = f"❌ Wiki 發布失敗：{wiki_res.get('error', '未知錯誤')}"
            await _reply_or_edit(
                bot,
                chat_id,
                status_msg,
                err_reply,
                reply_markup=get_summary_quick_reply_keyboard(),
            )
        return

    sys_p, usr_p = build_transform_prompt(action_type, raw_content, language=language)
    transformed = await run_blocking(
        call_gpt_api,
        usr_p,
        [{"role": "system", "content": sys_p}],
        selected_model=selected_model,
    )
    if not isinstance(transformed, str) or not transformed.strip():
        await _reply_or_edit(bot, chat_id, status_msg, "⚠️ AI 模型暫時無回應，請稍後再試。", reply_markup=get_summary_quick_reply_keyboard())
        return

    if action_type == "social":
        transformed = clean_social_post_output(transformed)
        if not transformed.strip():
            await _reply_or_edit(bot, chat_id, status_msg, "⚠️ AI 模型暫時無回應，請稍後再試。", reply_markup=get_summary_quick_reply_keyboard())
            return

    history.setdefault("messages", []).append({"role": "user", "content": user_message_text or f"轉換風格: {action_type}"})
    history["messages"].append({"role": "assistant", "content": transformed})
    target_chat_state["conversation_history"] = history
    await _delete_msg(bot, chat_id, status_msg)

    if action_type == "social":
        if len(transformed) <= 4000:
            await bot.send_message(chat_id=chat_id, text=transformed, reply_markup=get_summary_quick_reply_keyboard())
        else:
            for i in range(0, len(transformed), 4000):
                markup = get_summary_quick_reply_keyboard() if (i + 4000 >= len(transformed)) else None
                await bot.send_message(chat_id=chat_id, text=transformed[i : i + 4000], reply_markup=markup)
    else:
        await _send_telegram_formatted(
            bot,
            chat_id,
            transformed,
            reply_markup=get_summary_quick_reply_keyboard(),
        )


async def handle_start(update, context):
    return await handle("start", update, context)


async def handle_help(update, context):
    return await handle("help", update, context)


async def handle_model(update, context):
    return await handle("model", update, context)


async def handle_boa(update, context):
    return await handle("boa", update, context)


async def handle_tarot(update, context):
    return await handle("tarot", update, context)


async def handle_yiyu(update, context):
    return await handle("yiyu", update, context)


async def handle_yinyuan(update, context):
    return await handle("yinyuan", update, context)


async def handle_box(update, context):
    return await handle("box", update, context)


async def handle_boxstats(update, context):
    return await handle("boxstats", update, context)


async def handle_wiki(update, context):
    return await handle("wiki", update, context)


async def handle_wikiread(update, context):
    return await handle("wikiread", update, context)


async def handle_language(update, context):
    return await handle("language", update, context)


async def handle_clear_context(update, context):
    return await handle("clear_context", update, context)


async def handle_show_context(update, context):
    return await handle("show_context", update, context)


async def handle_adfilter(update, context):
    return await handle("adfilter", update, context)


async def handle_apikey(update, context):
    return await handle("apikey", update, context)


async def handle_summarize(update, context):
    return await handle("summarize", update, context)


async def handle_file(update, context):
    return await handle("file", update, context)


async def handle_yt2audio(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_user_authorized(user_id):
        await context.bot.send_message(chat_id=chat_id, text="Sorry, you are not authorized to use this bot.")
        return

    user_input = (update.message.text or "").split()
    if len(user_input) < 2:
        await context.bot.send_message(chat_id=chat_id, text="請提供一個影片的 URL。例如：/yt2audio 影片URL")
        return

    url = user_input[1]
    if not await run_blocking(is_safe_url, url):
        await context.bot.send_message(chat_id=chat_id, text="不支援或受保護的私有/內部網路網址。")
        return
    unsupported_reason = get_unsupported_media_url_reason(url)
    if unsupported_reason:
        logger.warning(
            "Rejected /yt2audio unsupported URL (chat_id=%s, user_id=%s, url=%s): %s",
            chat_id,
            user_id,
            url,
            unsupported_reason.replace("\n", " | "),
        )
        await context.bot.send_message(chat_id=chat_id, text=unsupported_reason)
        return

    processing_message = None
    if show_processing:
        processing_message = await context.bot.send_message(chat_id=chat_id, text="處理中，請稍候...")

    output_path = None
    try:
        async def _download_audio():
            return await run_blocking(download_video_audio, url)

        output_path = await asyncio.wait_for(_download_audio(), timeout=URL_PROCESSING_TIMEOUT_SECONDS)
        with open(output_path, "rb") as audio:
            await context.bot.send_audio(chat_id=chat_id, audio=audio)
        await _delete_msg(context.bot, chat_id, processing_message)
    except TimeoutError:
        logger.warning(
            "Timeout in handle_yt2audio after %.0fs (chat_id=%s, user_id=%s, url=%s)",
            URL_PROCESSING_TIMEOUT_SECONDS,
            chat_id,
            user_id,
            url,
        )
        await _reply_or_edit(
            context.bot,
            chat_id,
            processing_message,
            f"⏱️ 音訊下載逾時（超過 {int(URL_PROCESSING_TIMEOUT_SECONDS)} 秒未完成），已略過此請求。\n排查代碼：URL_PROCESSING_TIMEOUT",
        )
    except Exception as e:
        logger.warning("Error in handle_yt2audio (url=%s): %s", url, e, exc_info=True)
        err_msg = str(e) if isinstance(e, ValueError) and "排查代碼：" in str(e) else "下載或傳送音頻失敗。請檢查輸入的影片 URL 是否正確（若為頻道或播放清單網址請改貼單支影片 URL）。"
        await _reply_or_edit(context.bot, chat_id, processing_message, err_msg)
    finally:
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except Exception:
                pass


async def handle_yt2text(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_user_authorized(user_id):
        await context.bot.send_message(chat_id=chat_id, text="Sorry, you are not authorized to use this bot.")
        return

    user_input = (update.message.text or "").split()
    if len(user_input) < 2:
        await context.bot.send_message(chat_id=chat_id, text="請提供一個影片的 URL。例如：/yt2text 影片URL")
        return

    url = user_input[1]
    if not await run_blocking(is_safe_url, url):
        await context.bot.send_message(chat_id=chat_id, text="不支援或受保護的私有/內部網路網址。")
        return
    unsupported_reason = get_unsupported_media_url_reason(url)
    if unsupported_reason:
        logger.warning(
            "Rejected /yt2text unsupported URL (chat_id=%s, user_id=%s, url=%s): %s",
            chat_id,
            user_id,
            url,
            unsupported_reason.replace("\n", " | "),
        )
        await context.bot.send_message(chat_id=chat_id, text=unsupported_reason)
        return

    processing_message = None
    if show_processing:
        processing_message = await context.bot.send_message(chat_id=chat_id, text="處理中，請稍候...")

    try:
        async def _extract_transcript():
            return await run_blocking(retrieve_video_transcript_from_url, url)

        output_chunks = await asyncio.wait_for(_extract_transcript(), timeout=URL_PROCESSING_TIMEOUT_SECONDS)

        if is_extraction_error(output_chunks):
            await _reply_or_edit(context.bot, chat_id, processing_message, output_chunks[0])
            return
        if not output_chunks:
            await _reply_or_edit(context.bot, chat_id, processing_message, "未能擷取任何文字內容。")
            return

        content = "\n".join(output_chunks) + "\n"
        bio = io.BytesIO(content.encode("utf-8"))
        bio.name = "transcript.txt"
        await _delete_msg(context.bot, chat_id, processing_message)
        await context.bot.send_document(chat_id=chat_id, document=bio, filename="transcript.txt")
    except TimeoutError:
        logger.warning(
            "Timeout in handle_yt2text after %.0fs (chat_id=%s, user_id=%s, url=%s)",
            URL_PROCESSING_TIMEOUT_SECONDS,
            chat_id,
            user_id,
            url,
        )
        await _reply_or_edit(
            context.bot,
            chat_id,
            processing_message,
            f"⏱️ 影片轉文字逾時（超過 {int(URL_PROCESSING_TIMEOUT_SECONDS)} 秒未完成），已略過此請求。\n排查代碼：URL_PROCESSING_TIMEOUT",
        )
    except Exception as e:
        logger.warning("Error in handle_yt2text (url=%s): %s", url, e, exc_info=True)
        await _reply_or_edit(context.bot, chat_id, processing_message, "下載或轉換文本失敗。請檢查輸入的影片 URL 是否正確（若為頻道或播放清單網址請改貼單支影片 URL）。")


async def handle_button_click(update, context):
    """處理按鈕點擊事件，包含 API Key、語言、模型、廣告過濾與 Quick Reply。"""
    query = update.callback_query
    user_id = update.effective_user.id if update.effective_user else None
    if not _is_user_authorized(user_id):
        await query.answer("Sorry, you are not authorized to use this bot.", show_alert=True)
        return
    await query.answer()

    if query.data.startswith("apikey:"):
        chat = update.effective_chat
        if not chat or chat.type != "private":
            await query.edit_message_text("🔒 為避免金鑰外洩，請私訊機器人使用 /apikey 管理您的個人 API Key。")
            return

        sub_action = query.data.split(":", 1)[1]
        manager = await run_blocking(get_api_key_manager)

        if sub_action == "create":
            base_url, _ = await run_blocking(resolve_api_base_url)
            try:
                result = await run_blocking(manager.create_key, user_id)
            except KeyAlreadyExistsError:
                await query.edit_message_text(
                    text=(
                        "ℹ️ <b>您目前已有一把有效 API Key</b>\n\n"
                        "每位用戶僅限保留 1 把有效金鑰。若需更換或遺失原金鑰，請點擊下方「🔄 Rotate 輪換金鑰」。"
                    ),
                    reply_markup=_build_apikey_status_keyboard(has_key=True),
                    parse_mode="HTML",
                )
                return
            await query.edit_message_text(
                text=_format_issued_apikey_html(result, base_url, is_rotated=False),
                reply_markup=_build_apikey_status_keyboard(has_key=True),
                parse_mode="HTML",
            )
            return

        if sub_action == "rotate_confirm":
            await query.edit_message_text(
                text=(
                    "⚠️ <b>確定要輪換 API Key 嗎？</b>\n\n"
                    "輪換後<b>舊金鑰將立即失效</b>，使用舊金鑰的服務會收到 401。"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ 確認輪換", callback_data="apikey:rotate_exec"),
                    InlineKeyboardButton("❌ 取消", callback_data="apikey:cancel"),
                ]]),
                parse_mode="HTML",
            )
            return

        if sub_action == "rotate_exec":
            base_url, _ = await run_blocking(resolve_api_base_url)
            try:
                result = await run_blocking(manager.rotate_key, user_id)
            except KeyNotFoundError:
                await query.edit_message_text(
                    text=(
                        "ℹ️ <b>目前沒有可輪換的 API Key</b>\n\n"
                        "您的金鑰可能尚未建立或已被撤銷，請先點擊下方「🔑 產生我的 API Key」。"
                    ),
                    reply_markup=_build_apikey_status_keyboard(has_key=False),
                    parse_mode="HTML",
                )
                return
            await query.edit_message_text(
                text=_format_issued_apikey_html(result, base_url, is_rotated=True),
                reply_markup=_build_apikey_status_keyboard(has_key=True),
                parse_mode="HTML",
            )
            return

        if sub_action == "revoke_confirm":
            await query.edit_message_text(
                text=(
                    "⚠️ <b>確定要撤銷目前的 API Key 嗎？</b>\n\n"
                    "撤銷後該金鑰將<b>立即失效</b>，使用此金鑰的服務會收到 401。"
                ),
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ 確認撤銷", callback_data="apikey:revoke_exec"),
                    InlineKeyboardButton("❌ 取消", callback_data="apikey:cancel"),
                ]]),
                parse_mode="HTML",
            )
            return

        if sub_action == "revoke_exec":
            revoked = await run_blocking(manager.revoke_key, user_id)
            status_msg = "🗑️ <b>您的 API Key 已撤銷並立即失效。</b>" if revoked else "ℹ️ <b>目前沒有有效中的 API Key。</b>"
            await query.edit_message_text(
                text=f"{status_msg}\n\n若需要重新存取 Web API，可點擊下方按鈕重新產生。",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 產生我的 API Key", callback_data="apikey:create")]
                ]),
                parse_mode="HTML",
            )
            return

        if sub_action == "curl":
            base_url, _ = await run_blocking(resolve_api_base_url)
            curl_guide_escaped = html.escape(build_curl_usage_guide(base_url))
            base_url_escaped = html.escape(base_url)
            has_key = (await run_blocking(manager.get_key_metadata, user_id)) is not None
            await query.edit_message_text(
                text=(
                    "📖 <b>【Web API cURL 使用教學】</b>\n\n"
                    f"🌐 <b>API 端點：</b><code>{base_url_escaped}</code>\n"
                    "🔑 請將範例中的 <code>&lt;YOUR_API_KEY&gt;</code> 替換為您的個人金鑰：\n"
                    f"<pre><code>{curl_guide_escaped}</code></pre>"
                ),
                reply_markup=_build_apikey_status_keyboard(has_key=has_key),
                parse_mode="HTML",
            )
            return

        if sub_action == "cancel":
            await query.edit_message_text(text="已取消操作，現有 API Key 不受影響。")
            return

    if query.data.startswith("lang_"):
        language = query.data.split("_", 1)[1]
        context.user_data["language"] = language
        lang_name = SUPPORTED_LANGUAGES.get(language, language)
        await query.edit_message_text(
            text=f"✅ 語言已切換為: {lang_name}\nLanguage switched to: {lang_name}"
        )
        return

    if query.data.startswith("model_"):
        selected_model = query.data[6:]
        available_models = get_available_models()
        if selected_model in available_models:
            context.user_data["selected_model"] = selected_model
            await query.edit_message_text(text=f"✅ 模型已切換為: {selected_model}")
        else:
            await query.edit_message_text(text=f"❌ 模型不可用: {selected_model}")
        return

    if query.data.startswith("set_adfilter:"):
        action = query.data.split(":", 1)[1]
        if action == "on":
            context.user_data["ad_filter"] = True
            await query.edit_message_text("🛡️ 廣告決策過濾已更新為：🟢 已開啟 (預設)")
        else:
            context.user_data["ad_filter"] = False
            await query.edit_message_text("🛡️ 廣告決策過濾已更新為：🔴 已關閉")
        return

    if query.data.startswith("batch:"):
        parts = query.data.split(":", 2)
        if len(parts) != 3:
            return
        batch_id, batch_action = parts[1], parts[2]
        chat_state = _get_chat_state(context)
        _evict_expired_chat_items(chat_state, "batch_intent_")
        saved = chat_state.get(f"batch_intent_{batch_id}")
        if not saved:
            await query.edit_message_text("⌛ 此批次連結確認已過期，請重新貼上連結。")
            return

        if batch_action == "cancel":
            chat_state.pop(f"batch_intent_{batch_id}", None)
            await query.edit_message_text("🗑️ 已取消此批次處理。")
            return

        if saved.get("status") == "running":
            await query.answer("⏳ 此批次正在處理中，請稍候...", show_alert=False)
            return

        chat_id = update.effective_chat.id
        saved["status"] = "running"
        try:
            if batch_action == "individual":
                await _execute_batch_individual(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    batch_id=batch_id,
                    saved=saved,
                    urls_to_run=list(saved.get("urls") or []),
                )
            elif batch_action == "retry_individual":
                await _execute_batch_individual(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    batch_id=batch_id,
                    saved=saved,
                    urls_to_run=list(saved.get("failed_urls") or []),
                )
            elif batch_action in ("digest", "compare"):
                await _execute_batch_synthesis(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    batch_id=batch_id,
                    saved=saved,
                    mode=batch_action,
                    urls_to_extract=list(saved.get("urls") or []),
                )
            elif batch_action in ("retry_digest", "retry_compare"):
                mode = batch_action.split("_", 1)[1]
                await _execute_batch_synthesis(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    batch_id=batch_id,
                    saved=saved,
                    mode=mode,
                    urls_to_extract=list(saved.get("failed_urls") or []),
                )
            elif batch_action in ("proceed_digest", "proceed_compare"):
                mode = batch_action.split("_", 1)[1]
                sources = list(saved.get("sources") or [])
                if not sources:
                    await query.edit_message_text("❌ 沒有可用的成功來源可供整合。")
                    chat_state.pop(f"batch_intent_{batch_id}", None)
                    return
                await _deliver_batch_synthesis_result(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    batch_id=batch_id,
                    saved=saved,
                    mode=mode,
                    sources=sources,
                )
            elif batch_action == "fallback_individual":
                sources = list(saved.get("sources") or [])
                language = context.user_data.get("language", "zh-TW")
                default_title = "Text Summary" if language == "en" else "短文之摘要"
                await query.edit_message_text(f"📑 改為對成功的 {len(sources)} 筆來源各自產出單篇摘要...")
                for src in sources:
                    await _deliver_extracted_or_ad_hidden(
                        bot=context.bot,
                        chat_id=chat_id,
                        user_id=user_id,
                        user_data=context.user_data,
                        chat_state=chat_state,
                        status_msg=None,
                        text_array=src["text_array"],
                        source_input=src["url"],
                        user_note=saved.get("user_note"),
                        default_title=default_title,
                        raw_title=src.get("title"),
                    )
                chat_state.pop(f"batch_intent_{batch_id}", None)
            elif batch_action == "transcript":
                await _execute_batch_transcript(
                    bot=context.bot,
                    chat_id=chat_id,
                    status_msg=query.message,
                    batch_id=batch_id,
                    chat_state=chat_state,
                    urls_to_run=list(saved.get("urls") or []),
                )
        except Exception as e:
            logger.warning("Batch action %s failed: %s", batch_action, e, exc_info=True)
            saved["status"] = "pending"
            await _reply_or_edit(context.bot, chat_id, query.message, f"❌ 批次處理發生錯誤：{e}")
        return

    if query.data.startswith("url_act:"):
        parts = query.data.split(":", 2)
        if len(parts) != 3:
            return
        retry_id, url_action = parts[1], parts[2]
        chat_state = _get_chat_state(context)
        _evict_expired_chat_items(chat_state, "url_retry_")
        saved = chat_state.get(f"url_retry_{retry_id}")
        if not saved:
            await query.edit_message_text("⌛ 此操作已過期，請重新傳送連結或文字。")
            return

        if url_action == "cancel":
            chat_state.pop(f"url_retry_{retry_id}", None)
            await query.edit_message_text("🗑️ 已略過此項目。")
            return

        if saved.get("status") == "running":
            await query.answer("⏳ 正在處理中，請稍候...", show_alert=False)
            return

        chat_id = update.effective_chat.id
        saved["status"] = "running"
        target_url = saved.get("url")
        user_note = saved.get("user_note")
        language = context.user_data.get("language", "zh-TW")
        default_title = "Text Summary" if language == "en" else "短文之摘要"

        try:
            if url_action == "chat_note":
                if not user_note:
                    await query.edit_message_text("⚠️ 沒有可討論的附帶文字。")
                    chat_state.pop(f"url_retry_{retry_id}", None)
                    return
                await query.edit_message_text("💬 正在針對您的文字備註與提問生成回覆...")
                selected_model = context.user_data.get("selected_model", None)
                answer = await run_blocking(call_gpt_api, user_note, None, selected_model=selected_model)
                clean_answer, _ = sanitize_model_output(answer or "")
                final_answer = clean_answer.strip() or (answer or "").strip() or "⚠️ AI 模型暫時無回應，請稍後再試。"
                await _delete_msg(context.bot, chat_id, query.message)
                for i in range(0, len(final_answer), 4000):
                    await context.bot.send_message(chat_id=chat_id, text=final_answer[i : i + 4000])
                chat_state.pop(f"url_retry_{retry_id}", None)
                return

            if url_action == "force_audio":
                await query.edit_message_text("🎙️ 正在強制下載影片音訊並以 Whisper 轉錄，請稍候...")
                text_array = await asyncio.wait_for(
                    run_blocking(audio_transcription, target_url),
                    timeout=URL_PROCESSING_TIMEOUT_SECONDS,
                )
                if is_extraction_error(text_array) or not text_array:
                    err = text_array[0] if text_array else "音頻轉錄失敗。"
                    saved["status"] = "pending"
                    rec_text, rec_kb = _build_url_recovery_reply(chat_state, target_url or "", err, user_note=user_note)
                    await query.edit_message_text(rec_text, reply_markup=rec_kb, parse_mode="HTML")
                    chat_state.pop(f"url_retry_{retry_id}", None)
                    return
                raw_title = await run_blocking(get_web_title, target_url, False)
                await _deliver_extracted_or_ad_hidden(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    text_array=text_array,
                    source_input=target_url,
                    user_note=user_note,
                    default_title=default_title,
                    raw_title=raw_title,
                )
                chat_state.pop(f"url_retry_{retry_id}", None)
                return

            if url_action == "retry":
                await query.edit_message_text("🔄 正在重新抓取與處理該連結，請稍候...")
                text_array, raw_title, err_msg = await _extract_url_for_batch(target_url)
                if err_msg or not text_array:
                    rec_text, rec_kb = _build_url_recovery_reply(
                        chat_state,
                        target_url or "",
                        err_msg or "⚠️ 仍無法取得內容。",
                        user_note=user_note,
                    )
                    await query.edit_message_text(rec_text, reply_markup=rec_kb, parse_mode="HTML")
                    chat_state.pop(f"url_retry_{retry_id}", None)
                    return
                await _deliver_extracted_or_ad_hidden(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=chat_state,
                    status_msg=query.message,
                    text_array=text_array,
                    source_input=target_url,
                    user_note=user_note,
                    default_title=default_title,
                    raw_title=raw_title,
                )
                chat_state.pop(f"url_retry_{retry_id}", None)
                return
        except TimeoutError:
            rec_text, rec_kb = _build_url_recovery_reply(
                chat_state,
                target_url or "",
                f"⏱️ 網址處理逾時（超過 {int(URL_PROCESSING_TIMEOUT_SECONDS)} 秒未完成）。\n排查代碼：URL_PROCESSING_TIMEOUT",
                user_note=user_note,
            )
            await query.edit_message_text(rec_text, reply_markup=rec_kb, parse_mode="HTML")
            chat_state.pop(f"url_retry_{retry_id}", None)
        except Exception as e:
            logger.warning("URL recovery action %s failed: %s", url_action, e, exc_info=True)
            saved["status"] = "pending"
            await query.edit_message_text(f"❌ 重試處理時發生錯誤：{e}")
        return

    if query.data.startswith("show_ad:"):
        chat_state = _get_chat_state(context)
        _evict_expired_ad_hidden(chat_state)
        cache_id = query.data.split(":", 1)[1]
        saved = chat_state.get(f"ad_hidden_{cache_id}")
        if not saved:
            await query.answer("此內容暫存已過期，請重新發送網址或文字。", show_alert=True)
            return

        chat_id = update.effective_chat.id
        status_msg = await query.message.reply_text("⚡ 正在為您強制生成摘要，請稍候...")
        try:
            text_array = saved["text_array"]
            user_input = saved["user_input"]
            user_note = saved.get("user_note")
            if is_url(user_input):
                original_url = user_input
                raw_title = await run_blocking(get_web_title, user_input, False)
            else:
                original_url = None
                raw_title = None
            language = context.user_data.get("language", "zh-TW")
            default_title = "Text Summary" if language == "en" else "短文之摘要"
            await _finalize_and_deliver_summary(
                bot=context.bot,
                chat_id=chat_id,
                user_id=user_id,
                user_data=context.user_data,
                chat_state=chat_state,
                status_msg=status_msg,
                text_array=text_array,
                original_url=original_url,
                raw_title=raw_title,
                user_note=user_note,
                default_title=default_title,
                source_label="text input",
                discord_prefix="🔔 新的摘要已生成：",
            )
        except Exception as e:
            logger.warning("Force summarize ad failed: %s", e)
            await _reply_or_edit(context.bot, chat_id, status_msg, "❌ 生成摘要失敗，請稍後再試。")
        return

    if query.data.startswith("quick_"):
        action_type = query.data[6:]
        chat_state = _get_chat_state(context)
        history = chat_state.get("conversation_history")
        if not history:
            await query.message.reply_text("⚠️ 目前沒有可轉換的摘要記錄，請先傳送網址或檔案進行摘要。")
            return

        chat_id = update.effective_chat.id
        init_text_map = {
            "image": "🎨 正在為您構思並繪製概念圖，請稍候...",
            "wiki": "📚 正在發布至 David888 Wiki 知識庫...",
        }
        status_msg = await query.message.reply_text(
            init_text_map.get(action_type, "⚡ 正在快速整理轉換中，請稍候...")
        )
        try:
            await _handle_quick_reply_action(
                bot=context.bot,
                chat_id=chat_id,
                user_data=context.user_data,
                chat_state=chat_state,
                history=history,
                action_type=action_type,
                status_msg=status_msg,
            )
        except Exception as e:
            logger.warning("Quick reply action %s failed: %s", action_type, e)
            await _reply_or_edit(context.bot, chat_id, status_msg, "❌ 快速轉換處理失敗，請稍後再試。")
        return


async def handle(action, update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id if update.effective_user else None

    if not _is_user_authorized(user_id):
        await context.bot.send_message(chat_id=chat_id, text="Sorry, you are not authorized to use this bot.")
        return

    processing_message = None
    if show_processing:
        processing_message = await context.bot.send_message(chat_id=chat_id, text="處理中，請稍候...")

    try:
        if action == "start":
            bot_name = get_bot_display_name()
            start_text = (
                f"👋 歡迎使用 **{bot_name}**！\n\n"
                "🤖 我是您的全能 AI 助理與內容摘要機器人，具備以下強大能力：\n\n"
                "• 💬 **自然流暢 AI 對話**：直接打字輸入任何問題，日常聊天、程式諮詢、問題解答即刻回應。\n"
                "• 📄 **全格式文件摘要**：支援 PDF、Word (DOCX)、Excel (XLSX)、PPTX、EPUB、CSV、TXT 拖曳即摘要。\n"
                "• 🎥 **1000+ 影音與 Podcast**：直接貼上 YouTube、Bilibili、TikTok、Twitch、Podcast 網址。\n"
                "• 🎙️ **Whisper ASR 聽寫**：預設輸出 `[MM:SS]` 精確時間軸逐字稿檔案。\n"
                "• 📚 **David888 Wiki 知識庫**：長篇深度報告與分析可發布為美麗排版網頁與投影片。\n"
                "• 📦 **888box 雲端資產轉存**：轉存遠端影音檔案並提供 CloudFront CDN 直鏈。\n"
                "• 🔮 **東方與西方占卜**：塔羅牌抽牌 (`/tarot`)、月老求籤與生肖合婚 (`/yiyu`)、解答之書 (`/boa`)。\n\n"
                "👉 輸入 `/help` 查看完整指令清單與使用範例！"
            )
            await _reply_or_edit(context.bot, chat_id, processing_message, start_text, parse_mode="Markdown")
            return

        if action == "help":
            help_text = (
                f"📖 **【{get_bot_display_name()} 使用指南與指令清單】**\n\n"
                "💡 **直接發送內容（無需輸入指令）**：\n"
                "• **文字問答/對話**：輸入任何問題（如「如何學習 Rust」、「幫我潤飾這段郵件」），AI 自然流暢對話。\n"
                "• **網址/影音摘要**：直接貼上 YouTube、Bilibili、TikTok 或新聞文章 URL 自動產出結構化摘要。\n"
                "• **網址附帶筆記/觀點**：貼上網址時可直接附帶自己的觀點、備註或疑問，Bot 會附加筆記區塊並由 AI 專段回應。\n"
                "• **文件摘要**：直接上傳 PDF、Word、Excel、PPT、EPUB、CSV 檔案即刻解析摘要。\n\n"
                "📋 **可用指令一覽**：\n"
                "• `/start` - 查看機器人介紹與功能總覽\n"
                "• `/help` - 顯示此說明訊息\n"
                "• `/lang` - 切換語言 (繁體中文 ⇄ English)\n"
                "• `/model` - 切換/列出可用 LLM 模型\n"
                "• `/tarot [牌陣] [問題]` - 塔羅占卜 (支援單張/三張/鑽石/月亮/馬蹄鐵/塞爾特十字牌陣)\n"
                "• `/yiyu [模式] [問題]` - 月老姻緣求籤 / 生肖合婚契合度測算\n"
                "• `/boa` - Book of Answers 解答之書\n"
                "• `/wiki [標題/內容]` - 發布至 David888 Wiki 知識庫 (產出公開好讀版與投影片)\n"
                "• `/wikiread <路徑>` - 讀取 David888 Wiki 頁面內容\n"
                "• `/box <URL> [標題]` - 將遠端影片/音訊/檔案轉存至 888box 雲端\n"
                "• `/boxstats` - 查看 888box 資產統計\n"
                "• `/adfilter` - 查看或切換 Clef 廣告決策過濾\n"
                "• `/context` - 顯示當前對話上下文與問答輪數\n"
                "• `/clear` - 清除對話歷史與摘要記錄\n"
                "• `/yt2audio <URL>` - 下載影片音頻 (MP3)\n"
                "• `/yt2text <URL>` - 將影片音訊轉為帶時間戳逐字稿文字檔 (.txt)\n"
                "• `/apikey` - 產生/輪換個人 Web API Key 與查看 cURL 用法（限私訊）\n\n"
                "💬 摘要完成後，直接輸入問題即可對該內容進行深入續問！"
            )
            await _reply_or_edit(context.bot, chat_id, processing_message, help_text, parse_mode="Markdown")
            return

        if action == "language":
            current_lang = context.user_data.get("language", "zh-TW")
            current_lang_name = SUPPORTED_LANGUAGES.get(current_lang, "Unknown")
            keyboard = [[
                InlineKeyboardButton("🇹🇼 繁體中文", callback_data="lang_zh-TW"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            ]]
            await _reply_or_edit(
                context.bot,
                chat_id,
                processing_message,
                f"Current language / 當前語言: {current_lang_name}\n\nPlease select a language / 請選擇語言:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        if action == "clear_context":
            chat_state = _get_chat_state(context)
            chat_state["conversation_history"] = None
            chat_state["chat_history"] = None
            await _reply_or_edit(
                context.bot,
                chat_id,
                processing_message,
                "✅ 對話歷史已清除。下一次輸入將開始全新的對話或摘要。\nConversation history cleared.",
            )
            return

        if action == "show_context":
            chat_state = _get_chat_state(context)
            history = chat_state.get("conversation_history")
            chat_history = chat_state.get("chat_history") or []
            if history or chat_history:
                info_text = "📋 當前對話上下文 / Current Context:\n\n"
                if history:
                    info_text += f"📄 摘要來源: {history.get('source_url', 'N/A')}\n"
                    info_text += f"💬 摘要續問問答輪數: {len(history.get('messages', [])) // 2}\n"
                if chat_history:
                    info_text += f"💬 日常對話輪數: {len(chat_history) // 2}\n"
                info_text += "\n你可以直接打字聊天、繼續提問，或發送 URL 進行摘要。\nYou can continue chatting or send a new URL to summarize."
            else:
                info_text = "📭 目前沒有對話歷史。\nNo conversation history available."
            await _reply_or_edit(context.bot, chat_id, processing_message, info_text)
            return

        if action == "adfilter":
            current_pref = context.user_data.get("ad_filter", None)
            is_enabled = is_decision_ad_filter_enabled(current_pref)
            status_str = "🟢 已開啟 (預設)" if is_enabled else "🔴 已關閉"
            adfilter_text = (
                "🛡️ **【Clef 廣告決策過濾 (System One)】**\n\n"
                f"當前狀態：{status_str}\n"
                "決策節點：自建 Clef-Flash (<200ms) + 備援節點容錯\n"
                "超時設定：30 秒\n"
                "功能說明：自動偵測並隱藏推廣廣告、行銷垃圾與投資詐騙引流訊息，省去不必要的 AI 總結與 Token 消耗。"
            )
            keyboard = [[
                InlineKeyboardButton("🟢 開啟過濾", callback_data="set_adfilter:on"),
                InlineKeyboardButton("🔴 關閉過濾", callback_data="set_adfilter:off"),
            ]]
            await _reply_or_edit(
                context.bot,
                chat_id,
                processing_message,
                adfilter_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
            )
            return

        if action == "apikey":
            chat = update.effective_chat
            if not chat or chat.type != "private":
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    "🔒 為避免金鑰外洩，請私訊機器人使用 /apikey 管理您的個人 API Key。",
                )
                return

            manager = await run_blocking(get_api_key_manager)
            meta = await run_blocking(manager.get_key_metadata, user_id)
            resolved_url, source = await run_blocking(resolve_api_base_url)
            source_labels = {
                "env": "環境變數 API_PUBLIC_URL",
                "observed": "外部請求自動偵測",
                "public_ip": "公網 IP 自動偵測",
                "localhost": "本機預設位址",
            }
            source_label = source_labels.get(source, source)
            base_url_escaped = html.escape(resolved_url)
            source_escaped = html.escape(source_label)

            if meta is None:
                apikey_text = (
                    "🔑 <b>【個人 Web API Key 管理】</b>\n\n"
                    "目前尚未產生 API Key。\n"
                    "📌 每位 Telegram 用戶僅限 <b>1 把有效金鑰</b>（採 SHA-256 雜湊儲存，不保存明文）。\n\n"
                    f"🌐 <b>偵測 API 端點：</b><code>{base_url_escaped}</code>（來源：{source_escaped}）"
                )
                reply_markup = _build_apikey_status_keyboard(has_key=False)
            else:
                masked_escaped = html.escape(meta.get("masked_key") or "")
                created_escaped = html.escape(str(meta.get("created_at") or "N/A"))
                lines = [
                    "🔑 <b>【個人 Web API Key 管理】</b>\n",
                    f"• 遮罩金鑰：<code>{masked_escaped}</code>",
                    f"• 建立時間：<code>{created_escaped}</code>",
                ]
                if meta.get("rotated_at"):
                    lines.append(f"• 輪換時間：<code>{html.escape(str(meta['rotated_at']))}</code>")
                if meta.get("last_used_at"):
                    lines.append(f"• 最後使用：<code>{html.escape(str(meta['last_used_at']))}</code>")
                lines.extend([
                    f"• API 端點：<code>{base_url_escaped}</code>（來源：{source_escaped}）",
                    "",
                    "💡 若遺失原金鑰，請使用「Rotate 輪換金鑰」立即換發新金鑰（舊金鑰會即時失效）。",
                ])
                apikey_text = "\n".join(lines)
                reply_markup = _build_apikey_status_keyboard(has_key=True)

            await _reply_or_edit(
                context.bot,
                chat_id,
                processing_message,
                apikey_text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            return

        if action == "model":
            args = (update.message.text or "").split()[1:]
            current_model = context.user_data.get("selected_model", model)
            available_models = get_available_models()
            if args:
                requested_model = args[0].strip()
                if requested_model in available_models:
                    context.user_data["selected_model"] = requested_model
                    await _reply_or_edit(context.bot, chat_id, processing_message, f"✅ 模型已切換至: {requested_model}")
                else:
                    models_list = "\n".join(f"  • {m}" for m in available_models)
                    await _reply_or_edit(
                        context.bot,
                        chat_id,
                        processing_message,
                        f"❌ 模型不存在: {requested_model}\n\n📋 可用模型:\n{models_list}",
                    )
            else:
                keyboard = [
                    [InlineKeyboardButton(f"{'✅ ' if m == current_model else ''}{m}", callback_data=f"model_{m}")]
                    for m in available_models
                ]
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    f"🤖 當前模型: {current_model}\n\n請選擇模型:",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                )
            return

        if action == "boa":
            try:
                answer = await run_blocking(_fetch_boa_answer)
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    f"📖 解答之書 Book of Answers\n\n{answer}",
                )
            except Exception as e:
                logger.warning("Error fetching Book of Answers: %s", e)
                await _reply_or_edit(context.bot, chat_id, processing_message, "❌ 無法取得解答之書的回答")
            return

        if action == "tarot":
            message_text = update.message.text or ""
            parts = message_text.split(maxsplit=1)
            raw_input = parts[1].strip() if len(parts) > 1 else ""
            if not raw_input:
                await _reply_or_edit(context.bot, chat_id, processing_message, TAROT_HELP_TEXT, parse_mode="Markdown")
                return
            spread, question = parse_tarot_command(raw_input)
            if not question:
                await _reply_or_edit(context.bot, chat_id, processing_message, TAROT_HELP_TEXT, parse_mode="Markdown")
                return
            try:
                data = await run_blocking(ask_tarot_api, question, spread=spread)
                reply = format_tarot_reply(data, default_question=question, default_spread=spread)
            except Exception as e:
                logger.warning("Error calling tarot API: %s", e)
                reply = "❌ 塔羅占卜處理失敗，請稍後再試。"

            if len(reply) <= 4000:
                await _reply_or_edit(context.bot, chat_id, processing_message, reply)
            else:
                await _reply_or_edit(context.bot, chat_id, processing_message, reply[:4000])
                for i in range(4000, len(reply), 4000):
                    await context.bot.send_message(chat_id=chat_id, text=reply[i : i + 4000])
            return

        if action in ("yiyu", "yinyuan"):
            message_text = update.message.text or ""
            parts = message_text.split(maxsplit=1)
            raw_input = parts[1].strip() if len(parts) > 1 else ""
            if not raw_input:
                await _reply_or_edit(context.bot, chat_id, processing_message, YINYUAN_HELP_TEXT, parse_mode="Markdown")
                return
            mode, question, first_year, second_year = parse_yinyuan_command(raw_input)
            if not question:
                await _reply_or_edit(context.bot, chat_id, processing_message, YINYUAN_HELP_TEXT, parse_mode="Markdown")
                return
            try:
                data = await run_blocking(
                    ask_yinyuan_api,
                    question,
                    mode=mode,
                    first_year=first_year,
                    second_year=second_year,
                )
                reply = format_yinyuan_reply(data, default_question=question, mode=mode)
            except Exception as e:
                logger.warning("Error calling yinyuan API: %s", e)
                reply = "❌ 姻緣測算處理失敗，請稍後再試。"

            if len(reply) <= 4000:
                await _reply_or_edit(context.bot, chat_id, processing_message, reply)
            else:
                await _reply_or_edit(context.bot, chat_id, processing_message, reply[:4000])
                for i in range(4000, len(reply), 4000):
                    await context.bot.send_message(chat_id=chat_id, text=reply[i : i + 4000])
            return

        if action == "box":
            if user_id is None or not is_admin_user(user_id):
                await _reply_or_edit(context.bot, chat_id, processing_message, "🔒 888box 轉存功能僅限管理員使用。")
                return
            user_input = (update.message.text or "").split(maxsplit=2)
            if len(user_input) < 2:
                box_help = (
                    "📦 <b>【888box 資產轉存工具】</b>\n\n"
                    "用法範例：\n"
                    "• <code>/box &lt;URL&gt;</code>（轉存遠端影片、音訊、圖片或檔案）\n"
                    "• <code>/box &lt;URL&gt; 我的檔案標題</code>（指定標題轉存）\n"
                    "• <code>/boxstats</code>（查看當前儲存統計）\n\n"
                    "轉存成功後將提供 CloudFront CDN 直鏈與 888box 分享連結！"
                )
                await _reply_or_edit(context.bot, chat_id, processing_message, box_help, parse_mode="HTML")
                return

            target_url = user_input[1]
            title = user_input[2] if len(user_input) > 2 else ""
            res = await run_blocking(upload_url_to_box, target_url, title=title)
            if res.get("success"):
                reply = (
                    "✅ <b>【888box 轉存成功】</b>\n\n"
                    f"🆔 資源 ID：<code>{html.escape(str(res.get('id', '')))}</code>\n"
                    f"🔗 CDN 直鏈：{html.escape(str(res.get('url', '')))}\n"
                    f"🌐 分享頁面：{html.escape(str(res.get('share_url', '')))}"
                )
                await _reply_or_edit(context.bot, chat_id, processing_message, reply, parse_mode="HTML")
            else:
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    f"❌ 轉存失敗：{res.get('error', '未知錯誤')}",
                )
            return

        if action == "boxstats":
            if user_id is None or not is_admin_user(user_id):
                await _reply_or_edit(context.bot, chat_id, processing_message, "🔒 888box 統計查詢僅限管理員使用。")
                return
            res = await run_blocking(get_box_stats)
            if res.get("success"):
                data = res.get("data", {})
                endpoint_used = res.get("endpoint", "https://box.david888.com")
                reply = (
                    "📊 <b>【888box 資產統計】</b>\n\n"
                    f"• 📦 總資產數：{data.get('total', 0)}\n"
                    f"• 🖼️ 圖片：{data.get('image', 0)}\n"
                    f"• 🎥 影片：{data.get('video', 0)}\n"
                    f"• 🎵 音訊：{data.get('audio', 0)}\n"
                    f"• 📄 檔案：{data.get('file', 0)}\n\n"
                    f"🌐 節點位址：{html.escape(str(endpoint_used))}"
                )
                await _reply_or_edit(context.bot, chat_id, processing_message, reply, parse_mode="HTML")
            else:
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    f"❌ 取得統計失敗：{res.get('error', '未知錯誤')}",
                )
            return

        if action == "wiki":
            args = (update.message.text or "").split(maxsplit=1)
            provided_text = args[1].strip() if len(args) > 1 else ""
            chat_state = _get_chat_state(context)
            history = chat_state.get("conversation_history")
            if not provided_text and history and history.get("summary"):
                title = history.get("title") or history.get("source_url", "AI 內容摘要")
                source_url = history.get("source_url")
                original_url = source_url if source_url and is_url(source_url) else None
                content = prepare_wiki_content(
                    title=title,
                    summary=history.get("summary", ""),
                    original_url=original_url,
                    raw_title=history.get("raw_title"),
                    user_note=history.get("user_note"),
                )
            elif provided_text:
                lines = provided_text.split("\n", 1)
                title = lines[0].lstrip("#").strip()
                content = lines[1].strip() if len(lines) > 1 else ""
            else:
                help_msg = (
                    "📚 <b>【David888 Wiki 知識庫發布工具】</b>\n\n"
                    "用法範例：\n"
                    "• <code>/wiki</code>（直接將剛生成的摘要發布到 Wiki 好讀版）\n"
                    "• <code>/wiki 我的文章標題\n內文...</code>（將自訂 Markdown 發布為 Wiki 頁面）\n"
                    "• <code>/wikiread &lt;路徑&gt;</code>（讀取 Wiki 頁面內容）\n\n"
                    "發布後自動產生美觀排版分享網址與簡報模式 (Slide Deck)！"
                )
                await _reply_or_edit(context.bot, chat_id, processing_message, help_msg, parse_mode="HTML")
                return

            res = await run_blocking(publish_wiki_page, content, title=title)
            if res.get("success"):
                reply = (
                    "📚 <b>【David888 Wiki 發布成功】</b>\n\n"
                    f"📝 頁面路徑：<code>{html.escape(str(res.get('path', '')))}</code>\n"
                    f"🌐 閱讀頁面：{html.escape(str(res.get('shareUrl', '')))}\n"
                    f"🖥️ 2D 簡報模式：{html.escape(str(res.get('presentUrl', '')))}\n"
                    f"📖 電子書模式：{html.escape(str(res.get('bookUrl', '')))}\n"
                    f"🎨 套用主題：<code>{html.escape(str(res.get('theme', 'tokyo-night')))}</code>"
                )
                await _reply_or_edit(context.bot, chat_id, processing_message, reply, parse_mode="HTML")
            else:
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    f"❌ Wiki 發布失敗：{res.get('error', '未知錯誤')}",
                )
            return

        if action == "wikiread":
            args = (update.message.text or "").split(maxsplit=1)
            if len(args) < 2:
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    "📖 請指定 Wiki 路徑，例如：<code>/wikiread test-page</code>",
                    parse_mode="HTML",
                )
                return

            path = args[1].strip().lstrip("/")
            res = await run_blocking(read_wiki_page, path)
            if res.get("success"):
                content = res.get("content", "")
                if len(content) <= 3800:
                    reply = f"📖 【Wiki 頁面內容：{path}】\n\n{content}"
                    await _reply_or_edit(context.bot, chat_id, processing_message, reply)
                else:
                    await _reply_or_edit(
                        context.bot,
                        chat_id,
                        processing_message,
                        f"📖 【Wiki 頁面：{path}】（長篇內容已轉為檔案發送）",
                    )
                    bio = io.BytesIO(content.encode("utf-8"))
                    safe_name = os.path.basename(path) or "wiki_page"
                    bio.name = f"{safe_name}.md"
                    await context.bot.send_document(chat_id=chat_id, document=bio, filename=bio.name)
            else:
                await _reply_or_edit(
                    context.bot,
                    chat_id,
                    processing_message,
                    f"❌ 讀取 Wiki 頁面失敗：{res.get('error', '未知錯誤')}",
                )
            return

        if action == "summarize":
            try:
                user_input = update.message.text or ""
                chat_state = _get_chat_state(context)
                history = chat_state.get("conversation_history")
                if is_conversation_followup(user_input, history):
                    language = context.user_data.get("language", "zh-TW")
                    selected_model = context.user_data.get("selected_model", None)
                    raw_content = build_quick_reply_source(history)

                    quick_intent = detect_quick_reply_intent(user_input)
                    if quick_intent:
                        await _handle_quick_reply_action(
                            bot=context.bot,
                            chat_id=chat_id,
                            user_data=context.user_data,
                            chat_state=chat_state,
                            history=history,
                            action_type=quick_intent,
                            user_message_text=user_input,
                            status_msg=processing_message,
                        )
                        return

                    orig_text = "\n".join(history.get("original_content", [])) if history.get("original_content") else raw_content
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant that answers questions about previously summarized content."},
                        {"role": "user", "content": f"Original content:\n{orig_text[:3000]}"},
                        {"role": "assistant", "content": f"Summary:\n{history.get('summary', '')[:2000]}"},
                    ]
                    for msg in history.get("messages", [])[-6:]:
                        messages.append(msg)

                    answer = await run_blocking(call_gpt_api, user_input, messages, selected_model=selected_model)
                    if not isinstance(answer, str) or not answer.strip():
                        await _reply_or_edit(
                            context.bot,
                            chat_id,
                            processing_message,
                            "⚠️ AI 模型暫時無回應，請稍後再試。",
                            reply_markup=get_summary_quick_reply_keyboard(),
                        )
                        return

                    history["messages"].append({"role": "user", "content": user_input})
                    history["messages"].append({"role": "assistant", "content": answer})
                    chat_state["conversation_history"] = history
                    await _delete_msg(context.bot, chat_id, processing_message)

                    if len(answer) <= 4000:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"💬 續問回答:\n\n{answer}",
                            reply_markup=get_summary_quick_reply_keyboard(),
                        )
                    else:
                        for i in range(0, len(answer), 4000):
                            markup = get_summary_quick_reply_keyboard() if (i + 4000 >= len(answer)) else None
                            await context.bot.send_message(chat_id=chat_id, text=answer[i : i + 4000], reply_markup=markup)
                    return

                parsed_multi = parse_urls_and_user_note(user_input)
                if len(parsed_multi["urls"]) >= 2:
                    valid_urls, rejected_items = await run_blocking(_preflight_check_urls, parsed_multi["urls"])
                    if not valid_urls:
                        err_lines = ["❌ <b>偵測到的多個連結目前皆無法處理：</b>"]
                        for item in rejected_items:
                            short_u = item["url"] if len(item["url"]) <= 60 else f"{item['url'][:57]}..."
                            err_lines.append(
                                f"• <code>{html.escape(short_u)}</code>\n"
                                f"  原因：<code>{html.escape(item['code'])}</code>\n"
                                f"  💡 建議：{html.escape(item['suggestion'])}"
                            )
                        reply_markup = None
                        if parsed_multi["user_note"]:
                            _evict_expired_chat_items(chat_state, "url_retry_")
                            retry_id = str(uuid.uuid4())[:8]
                            chat_state[f"url_retry_{retry_id}"] = {
                                "url": None,
                                "user_note": parsed_multi["user_note"],
                                "status": "pending",
                                "created_at": time.time(),
                            }
                            err_lines.append("\n偵測到您有附帶文字備註，請問是否改為僅就您的文字進行 AI 討論？")
                            reply_markup = InlineKeyboardMarkup([
                                [InlineKeyboardButton("💬 僅針對我的文字與 AI 討論", callback_data=f"url_act:{retry_id}:chat_note")],
                                [InlineKeyboardButton("❌ 關閉", callback_data=f"url_act:{retry_id}:cancel")],
                            ])
                        await _reply_or_edit(
                            context.bot,
                            chat_id,
                            processing_message,
                            "\n".join(err_lines),
                            reply_markup=reply_markup,
                            parse_mode="HTML",
                        )
                        return

                    _evict_expired_chat_items(chat_state, "batch_intent_")
                    batch_id = str(uuid.uuid4())[:8]
                    chat_state[f"batch_intent_{batch_id}"] = {
                        "urls": valid_urls,
                        "rejected": rejected_items,
                        "user_note": parsed_multi["user_note"],
                        "status": "pending",
                        "created_at": time.time(),
                    }
                    card_text, card_kb = _build_batch_intent_card(
                        valid_urls=valid_urls,
                        rejected_items=rejected_items,
                        dropped_count=parsed_multi["dropped_count"],
                        user_note=parsed_multi["user_note"],
                        batch_id=batch_id,
                    )
                    await _reply_or_edit(
                        context.bot,
                        chat_id,
                        processing_message,
                        card_text,
                        reply_markup=card_kb,
                        parse_mode="HTML",
                    )
                    return

                extracted_url, user_note = parse_url_and_user_note(user_input)

                if not extracted_url and not is_explicit_summary_request(user_input):
                    chat_history = chat_state.get("chat_history") or []
                    language = context.user_data.get("language", "zh-TW")
                    sys_lang = "繁體中文 (Traditional Chinese)" if language == "zh-TW" else "English"
                    system_prompt = (
                        "You are a helpful, friendly, and highly intelligent AI assistant. "
                        f"Respond naturally, concisely, and accurately in {sys_lang}. "
                        "Support markdown formatting for code, lists, and bold text when helpful."
                    )
                    messages = [{"role": "system", "content": system_prompt}]
                    for msg in chat_history[-6:]:
                        messages.append(msg)

                    selected_model = context.user_data.get("selected_model", None)
                    raw_answer = await run_blocking(call_gpt_api, user_input, messages, selected_model=selected_model)
                    if not isinstance(raw_answer, str) or not raw_answer.strip():
                        await _reply_or_edit(context.bot, chat_id, processing_message, "⚠️ AI 模型暫時無回應，請稍後再試。")
                        return

                    clean_answer, parsed_title = sanitize_model_output(raw_answer)
                    answer = clean_answer.strip() or raw_answer.strip()

                    chat_history.append({"role": "user", "content": user_input})
                    chat_history.append({"role": "assistant", "content": answer})
                    chat_state["chat_history"] = chat_history[-10:]

                    # Only publish to Wiki when user explicitly mentions Wiki (never auto-publish private analysis/chats)
                    if is_explicit_wiki_publish_request(user_input):
                        try:
                            wiki_title = parsed_title or user_input[:25]
                            wiki_res = await run_blocking(publish_wiki_page, answer, title=wiki_title)
                            if wiki_res.get("success"):
                                answer += (
                                    "\n\n📚 【David888 Wiki 完整排版與簡報】\n"
                                    f"🌐 線上好讀版：{wiki_res.get('shareUrl')}\n"
                                    f"🖥️ 2D 簡報模式：{wiki_res.get('presentUrl')}\n"
                                    f"📖 電子書模式：{wiki_res.get('bookUrl')}"
                                )
                        except Exception as e:
                            logger.debug("Auto publish to wiki failed: %s", e)

                    await _delete_msg(context.bot, chat_id, processing_message)
                    if len(answer) <= 4000:
                        await context.bot.send_message(chat_id=chat_id, text=answer)
                    else:
                        for i in range(0, len(answer), 4000):
                            await context.bot.send_message(chat_id=chat_id, text=answer[i : i + 4000])
                    return

                if extracted_url:
                    user_input = extracted_url

                async def _extract_input():
                    return await run_blocking(process_user_input, user_input)

                try:
                    text_array = await asyncio.wait_for(_extract_input(), timeout=URL_PROCESSING_TIMEOUT_SECONDS)
                except TimeoutError:
                    logger.warning(
                        "URL/content extraction timed out after %.0fs (chat_id=%s, user_id=%s, input=%s)",
                        URL_PROCESSING_TIMEOUT_SECONDS,
                        chat_id,
                        user_id,
                        user_input,
                    )
                    timeout_err = (
                        f"⏱️ 網址處理逾時（超過 {int(URL_PROCESSING_TIMEOUT_SECONDS)} 秒未完成），已略過此項目以避免阻塞後續排隊訊息。\n"
                        "原因：來源網站回應過慢或媒體檔案過大無法於時限內擷取。\n"
                        "排查代碼：URL_PROCESSING_TIMEOUT"
                    )
                    rec_text, rec_kb = _build_url_recovery_reply(chat_state, user_input, timeout_err, user_note=user_note)
                    await _reply_or_edit(
                        context.bot,
                        chat_id,
                        processing_message,
                        rec_text,
                        reply_markup=rec_kb,
                        parse_mode="HTML",
                    )
                    return

                if isinstance(text_array, tuple):
                    if len(text_array) == 2 and not text_array[0]:
                        logger.info(
                            "Content extraction rejected/failed (chat_id=%s, user_id=%s, input=%s): %s",
                            chat_id,
                            user_id,
                            user_input,
                            str(text_array[1]).replace("\n", " | "),
                        )
                        if is_url(user_input):
                            rec_text, rec_kb = _build_url_recovery_reply(
                                chat_state,
                                user_input,
                                str(text_array[1]),
                                user_note=user_note,
                            )
                            await _reply_or_edit(
                                context.bot,
                                chat_id,
                                processing_message,
                                rec_text,
                                reply_markup=rec_kb,
                                parse_mode="HTML",
                            )
                        else:
                            await _delete_msg(context.bot, chat_id, processing_message)
                            await context.bot.send_message(chat_id=chat_id, text=text_array[1])
                        return
                    text_array = text_array[0]

                if is_extraction_error(text_array):
                    logger.info(
                        "Content extraction sentinel error (chat_id=%s, user_id=%s, input=%s): %s",
                        chat_id,
                        user_id,
                        user_input,
                        str(text_array[0]).replace("\n", " | "),
                    )
                    if is_url(user_input):
                        rec_text, rec_kb = _build_url_recovery_reply(
                            chat_state,
                            user_input,
                            str(text_array[0]),
                            user_note=user_note,
                        )
                        await _reply_or_edit(
                            context.bot,
                            chat_id,
                            processing_message,
                            rec_text,
                            reply_markup=rec_kb,
                            parse_mode="HTML",
                        )
                    else:
                        await _delete_msg(context.bot, chat_id, processing_message)
                        await context.bot.send_message(chat_id=chat_id, text=text_array[0])
                    return

                if text_array:
                    language = context.user_data.get("language", "zh-TW")
                    default_title = "Text Summary" if language == "en" else "短文之摘要"
                    await _deliver_extracted_or_ad_hidden(
                        bot=context.bot,
                        chat_id=chat_id,
                        user_id=user_id,
                        user_data=context.user_data,
                        chat_state=chat_state,
                        status_msg=processing_message,
                        text_array=text_array,
                        source_input=user_input,
                        user_note=user_note,
                        default_title=default_title,
                    )
                else:
                    if is_url(user_input):
                        rec_text, rec_kb = _build_url_recovery_reply(
                            chat_state,
                            user_input,
                            "⚠️ 無法從此網址擷取到文字內容。",
                            user_note=user_note,
                        )
                        await _reply_or_edit(
                            context.bot,
                            chat_id,
                            processing_message,
                            rec_text,
                            reply_markup=rec_kb,
                            parse_mode="HTML",
                        )
                    else:
                        await _reply_or_edit(
                            context.bot,
                            chat_id,
                            processing_message,
                            "無法處理輸入的文本。請提供有效的網址、較長的文章內容，或直接輸入問題與我對話。",
                        )
            except Exception as e:
                logger.warning("Error in summarize action: %s", e, exc_info=True)
                await _reply_or_edit(context.bot, chat_id, processing_message, "處理您的請求時發生錯誤，請稍後再試。")
            return

        if action == "file":
            try:
                if not update.message.document and update.message.photo:
                    await _reply_or_edit(
                        context.bot,
                        chat_id,
                        processing_message,
                        "🖼️ 目前暫不支援純圖片 OCR 摘要，請上傳文字/文件檔（PDF、Word、Excel、PPT、EPUB、CSV、TXT）或音訊檔。",
                    )
                    return

                if not update.message.document:
                    raise ValueError("無法取得檔案")

                tg_file = await update.message.document.get_file()
                filename = update.message.document.file_name or ""
                raw_ext = os.path.splitext(filename)[1]
                ext = re.sub(r"[^a-zA-Z0-9._-]", "", raw_ext)
                clean_file_id = re.sub(r"[^a-zA-Z0-9_-]", "", tg_file.file_id)

                with tempfile.TemporaryDirectory(prefix="tg_file_") as tmp_dir:
                    file_path = os.path.join(tmp_dir, f"{clean_file_id}{ext}")
                    await tg_file.download_to_drive(file_path)

                    file_type_info = await run_blocking(detect_file_type, file_path)
                    file_group = file_type_info.get("group", "")
                    file_label = file_type_info.get("label", "")
                    file_desc = file_type_info.get("description", "")

                    if file_group == "audio" or file_label in ("mp3", "m4a", "wav", "flac", "ogg", "aac", "opus", "wma"):
                        progress = f"🎧 偵測到音訊檔案（{file_label.upper()}），正在使用 Whisper 進行語音轉錄..."
                        processing_message = await _reply_or_edit(context.bot, chat_id, processing_message, progress)

                        text = await run_blocking(transcribe_local_audio, file_path)
                        if not text:
                            raise ValueError("音訊轉文字未能辨識出任何內容，請確認音訊是否包含清晰語音。")

                        if len(text) > 1000:
                            bio = io.BytesIO(text.encode("utf-8"))
                            bio.name = f"{filename or 'audio'}_transcript.txt"
                            await context.bot.send_document(
                                chat_id=chat_id,
                                document=bio,
                                filename=bio.name,
                                caption="📄 音訊完整逐字稿（含時間戳記）",
                            )
                    elif file_group in ("executable", "image") or (
                        file_group == "archive" and ext.lower() not in (".docx", ".pptx", ".xlsx", ".epub", ".pdf")
                    ):
                        unsupported_msg = (
                            f"⚠️ 暫不支援的檔案格式：{file_desc} ({file_label})。\n"
                            "目前支援 PDF、Word、PPT、Excel、純文字、程式碼與各類常見音訊檔案。"
                        )
                        await _reply_or_edit(context.bot, chat_id, processing_message, unsupported_msg)
                        return
                    else:
                        processing_message = await _reply_or_edit(context.bot, chat_id, processing_message, "正在處理檔案...")
                        text = await run_blocking(convert_document_to_markdown, file_path)

                raw_title = filename or None
                await _finalize_and_deliver_summary(
                    bot=context.bot,
                    chat_id=chat_id,
                    user_id=user_id,
                    user_data=context.user_data,
                    chat_state=_get_chat_state(context),
                    status_msg=processing_message,
                    text_array=[text],
                    original_url=None,
                    raw_title=raw_title,
                    user_note=None,
                    default_title="文件摘要",
                    source_label=filename or "uploaded file",
                    discord_prefix="🔔 已成功處理一份文件，摘要內容如下：",
                )
            except Exception as e:
                logger.warning("Error processing file: %s", e, exc_info=True)
                await _reply_or_edit(context.bot, chat_id, processing_message, "處理檔案時發生錯誤，請稍後再試。")
            return

    except Exception as e:
        logger.error("Unhandled error in handle(%s): %s", action, e, exc_info=True)
        await _reply_or_edit(context.bot, chat_id, processing_message, "發生錯誤，請稍後再試。")


def clear_old_commands(telegram_token_arg):
    url = f"https://api.telegram.org/bot{telegram_token_arg}/deleteMyCommands"
    scopes = ["default", "all_private_chats", "all_group_chats", "all_chat_administrators"]
    for scope in scopes:
        try:
            requests.post(url, json={"scope": {"type": scope}}, timeout=WEB_REQUEST_TIMEOUT_SECONDS)
        except Exception as e:
            logger.debug("Exception clearing old commands for scope %s: %s", scope, e)


def set_my_commands(telegram_token_arg):
    clear_old_commands(telegram_token_arg)
    url = f"https://api.telegram.org/bot{telegram_token_arg}/setMyCommands"
    commands = [
        {"command": "start", "description": "確認機器人是否在線"},
        {"command": "help", "description": "顯示此幫助訊息"},
        {"command": "lang", "description": "切換語言 Switch language"},
        {"command": "model", "description": "切換/列出模型 Switch/List models"},
        {"command": "boa", "description": "解答之書 Book of Answers"},
        {"command": "tarot", "description": "塔羅占卜 Tarot reading"},
        {"command": "yiyu", "description": "月老姻緣 / 生肖合婚"},
        {"command": "context", "description": "顯示對話上下文 Show context"},
        {"command": "clear", "description": "清除對話歷史 Clear history"},
        {"command": "yt2audio", "description": "下載影片音頻（支援 YouTube、Vimeo、Bilibili 等）"},
        {"command": "yt2text", "description": "將影片轉成文字（支援 YouTube、Vimeo、Bilibili 等）"},
        {"command": "box", "description": "轉存 URL 至 888box 空間"},
        {"command": "boxstats", "description": "查看 888box 資產統計"},
        {"command": "wiki", "description": "發布至 David888 Wiki 知識庫"},
        {"command": "wikiread", "description": "讀取 David888 Wiki 頁面"},
        {"command": "adfilter", "description": "查看或切換廣告決策過濾"},
        {"command": "apikey", "description": "產生/輪換個人 API Key 與查看 cURL 用法"},
    ]
    try:
        response = requests.post(url, json={"commands": commands}, timeout=WEB_REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 200:
            logger.info("Commands set successfully.")
        else:
            logger.warning("Failed to set commands: %s", response.text)
    except Exception as e:
        err_msg = str(e)
        if telegram_token_arg and telegram_token_arg in err_msg:
            err_msg = err_msg.replace(telegram_token_arg, "[REDACTED]")
        logger.warning("Exception setting commands: %s", err_msg)


def _resolve_persistence_path() -> str:
    explicit = os.environ.get("BOT_PERSISTENCE_PATH", "").strip()
    if explicit:
        return explicit
    data_dir = get_data_dir()
    if data_dir:
        return os.path.join(data_dir, "bot_persistence.pkl")
    return ""


async def _on_application_error(update, context) -> None:
    """Log unhandled Telegram update errors with update context so polling continues cleanly."""
    logger.error(
        "Unhandled error while processing Telegram update %s: %s",
        getattr(update, "update_id", "unknown"),
        getattr(context, "error", "unknown"),
        exc_info=getattr(context, "error", None),
    )


def _build_bot_application(persistence_path: str = ""):
    builder = ApplicationBuilder().token(telegram_token).concurrent_updates(BOT_CONCURRENT_UPDATES)
    if persistence_path:
        try:
            parent_dir = os.path.dirname(os.path.abspath(persistence_path))
            os.makedirs(parent_dir, mode=0o700, exist_ok=True)
            builder = builder.persistence(PicklePersistence(filepath=persistence_path))
            logger.info("Telegram bot persistence enabled at %s", persistence_path)
        except Exception as exc:
            logger.warning("Failed to configure bot persistence at %s: %s", persistence_path, exc)

    application = builder.build()
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.PHOTO, handle_file))
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("lang", handle_language))
    application.add_handler(CommandHandler("language", handle_language))
    application.add_handler(CommandHandler("model", handle_model))
    application.add_handler(CommandHandler("boa", handle_boa))
    application.add_handler(CommandHandler("tarot", handle_tarot))
    application.add_handler(CommandHandler("yiyu", handle_yiyu))
    application.add_handler(CommandHandler("yinyuan", handle_yinyuan))
    application.add_handler(CommandHandler("box", handle_box))
    application.add_handler(CommandHandler("boxstats", handle_boxstats))
    application.add_handler(CommandHandler("wiki", handle_wiki))
    application.add_handler(CommandHandler("wikiread", handle_wikiread))
    application.add_handler(CommandHandler("adfilter", handle_adfilter))
    application.add_handler(CommandHandler("apikey", handle_apikey))
    application.add_handler(CommandHandler("clear", handle_clear_context))
    application.add_handler(CommandHandler("context", handle_show_context))
    application.add_handler(CommandHandler("yt2audio", handle_yt2audio))
    application.add_handler(CommandHandler("yt2text", handle_yt2text))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_summarize))
    application.add_handler(CallbackQueryHandler(handle_button_click))
    application.add_error_handler(_on_application_error)
    return application


async def main():
    from app.api import app, set_bot_ready

    try:
        persistence_path = _resolve_persistence_path()
        application = _build_bot_application(persistence_path)
        await run_blocking(set_my_commands, telegram_token)

        try:
            await application.initialize()
        except (pickle.UnpicklingError, EOFError, OSError, ValueError, ImportError, AttributeError) as p_err:
            if persistence_path and os.path.exists(persistence_path):
                quarantine = f"{persistence_path}.corrupt.{int(time.time())}"
                logger.warning("Corrupt persistence file %s (%s); quarantining to %s and rebuilding.", persistence_path, p_err, quarantine)
                try:
                    os.replace(persistence_path, quarantine)
                except OSError:
                    pass
                application = _build_bot_application(persistence_path)
                await application.initialize()
            else:
                raise
        await application.start()
        await application.updater.start_polling()
        set_bot_ready(True)
        print("🤖 Telegram Bot initialized and polling started.")

        api_port = int(os.environ.get("API_PORT", "8001"))
        config = uvicorn.Config(app, host="0.0.0.0", port=api_port, log_level="info")
        server = uvicorn.Server(config)

        print(f"🌐 FastAPI Web API starting on port {api_port}...")

        try:
            await server.serve()
        finally:
            set_bot_ready(False)
            print("Shutting down Telegram Bot...")
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
            print("👋 Telegram Bot stopped and resource cleanup completed.")

    except Exception as e:
        set_bot_ready(False)
        logger.error("Error during application startup: %s", e, exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
