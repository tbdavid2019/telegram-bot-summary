"""Telegram HTML formatting and safe chunked message delivery helpers."""

import re

from app.runtime import run_blocking
from app.services.content import _split_markdown_safely

_TELEGRAM_ALLOWED_TAGS = frozenset({"b", "i", "u", "s", "a", "code", "pre", "tg-spoiler"})
_ALLOWED_LINK_SCHEMES = ("http://", "https://", "tg://", "mailto:")


def format_for_telegram(markdown_text: str) -> str:
    """Convert Markdown into Telegram-compatible HTML subset without unescaping HTML entities."""
    if not markdown_text:
        return markdown_text

    try:
        import markdown
        from bs4 import BeautifulSoup, NavigableString

        html = markdown.markdown(markdown_text, extensions=["nl2br"])
        soup = BeautifulSoup(html, "html.parser")

        # 1. Normalize inline semantic tags first so decode_contents() preserves Telegram tags
        for strong in soup.find_all("strong"):
            strong.name = "b"
            strong.attrs = {}

        for em in soup.find_all("em"):
            em.name = "i"
            em.attrs = {}

        for strike in soup.find_all(["del", "strike"]):
            strike.name = "s"
            strike.attrs = {}

        for ins in soup.find_all("ins"):
            ins.name = "u"
            ins.attrs = {}

        # Sanitize <a> attributes (allow only safe href schemes)
        for anchor in soup.find_all("a"):
            href = (anchor.get("href") or "").strip()
            if href.lower().startswith(_ALLOWED_LINK_SCHEMES):
                anchor.attrs = {"href": href}
            else:
                anchor.unwrap()

        # 2. Convert structural/block tags using decode_contents() to keep inner inline formatting
        for br in soup.find_all("br"):
            br.replace_with(NavigableString("\n"))

        for hr in soup.find_all("hr"):
            hr.replace_with(NavigableString("\n----------\n"))

        for heading in reversed(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
            inner_html = heading.decode_contents().strip()
            heading.replace_with(BeautifulSoup(f"<b>{inner_html}</b>\n\n", "html.parser"))

        for li in reversed(soup.find_all("li")):
            inner_html = li.decode_contents().strip()
            li.replace_with(BeautifulSoup(f"• {inner_html}\n", "html.parser"))

        for lst in reversed(soup.find_all(["ul", "ol"])):
            lst.unwrap()

        for paragraph in reversed(soup.find_all("p")):
            inner_html = paragraph.decode_contents()
            paragraph.replace_with(BeautifulSoup(f"{inner_html}\n\n", "html.parser"))

        # 3. Strip/unwrap any remaining tags outside Telegram's allowed HTML subset
        for tag in reversed(soup.find_all(True)):
            if tag.name not in _TELEGRAM_ALLOWED_TAGS:
                tag.unwrap()
            elif tag.name == "code":
                classes = tag.get("class")
                tag.attrs = {"class": classes} if classes else {}
            elif tag.name != "a":
                tag.attrs = {}

        # 4. Keep HTML entities (&lt;, &gt;, &amp;) intact — NEVER unescape
        final_text = re.sub(r"\n{3,}", "\n\n", str(soup))
        return final_text.strip()
    except Exception as e:
        print(f"Error formatting for Telegram: {e}")
        return markdown_text


async def send_telegram_formatted(bot, chat_id, raw_text: str, reply_markup=None) -> None:
    """Split Markdown safely, format each chunk in a worker thread, and fall back per-chunk to plain text."""
    if not raw_text or not str(raw_text).strip():
        return

    chunks = _split_markdown_safely(str(raw_text), limit=3200)
    if not chunks:
        return

    total_chunks = len(chunks)
    for idx, chunk in enumerate(chunks):
        is_last_chunk = idx == total_chunks - 1
        chunk_markup = reply_markup if is_last_chunk else None

        formatted_chunk = await run_blocking(format_for_telegram, chunk)
        sent_html = False
        if formatted_chunk and str(formatted_chunk).strip() and len(formatted_chunk) <= 4000:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=formatted_chunk,
                    parse_mode="HTML",
                    reply_markup=chunk_markup,
                )
                sent_html = True
            except Exception as parse_err:
                print(
                    f"[WARN] Failed to send HTML formatted chunk {idx + 1}/{total_chunks} "
                    f"({parse_err}), falling back to plain text for this chunk..."
                )

        if not sent_html:
            if len(chunk) <= 4000:
                await bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    reply_markup=chunk_markup,
                )
            else:
                plain_parts = [chunk[i : i + 4000] for i in range(0, len(chunk), 4000)]
                for p_idx, plain_part in enumerate(plain_parts):
                    part_markup = chunk_markup if (p_idx == len(plain_parts) - 1) else None
                    await bot.send_message(
                        chat_id=chat_id,
                        text=plain_part,
                        reply_markup=part_markup,
                    )
