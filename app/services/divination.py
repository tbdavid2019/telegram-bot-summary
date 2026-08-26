"""Divination service integrating Tarot and Yinyuan endpoints from qimen API."""

import os
import requests

QIMEN_API_BASE_URL = os.environ.get("QIMEN_API_BASE_URL", "https://qi.david888.com").rstrip("/")
DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", os.environ.get("WEB_REQUEST_TIMEOUT_SECONDS", "60")))

SPREAD_NAMES = {
    "single": "單張牌指引 (Single Card)",
    "three": "三張牌牌陣 (Three Cards)",
    "diamond": "鑽石牌陣 (Diamond Spread)",
    "moon": "月亮牌陣 (Moon Spread)",
    "horseshoe": "馬蹄鐵牌陣 (Horseshoe Spread)",
    "celtic": "塞爾特十字牌陣 (Celtic Cross)",
}

SPREAD_ALIASES = {
    "single": "single",
    "1": "single",
    "one": "single",
    "單張": "single",
    "一張": "single",
    "three": "three",
    "3": "three",
    "三張": "three",
    "diamond": "diamond",
    "5": "diamond",
    "鑽石": "diamond",
    "moon": "moon",
    "4": "moon",
    "月亮": "moon",
    "horseshoe": "horseshoe",
    "7": "horseshoe",
    "馬蹄": "horseshoe",
    "馬蹄鐵": "horseshoe",
    "celtic": "celtic",
    "10": "celtic",
    "十字": "celtic",
    "塞爾特": "celtic",
    "塞爾特十字": "celtic",
}

TAROT_HELP_TEXT = """🔮 【塔羅占卜 Tarot Reading】

📖 指令格式：
`/tarot [牌陣] [你的問題]`

💡 使用示範：
• `/tarot 最近適合轉職嗎？`（預設三張牌牌陣 three）
• `/tarot single 今日運勢如何？`（指定單張牌 single）
• `/tarot three 感情未來走向與建議`（過去/現在/未來）
• `/tarot diamond 眼前這項投資該如何決策？`（鑽石牌陣）

🃏 支援牌陣：
• `single`（單張牌：每日運勢、快速是非）
• `three`（三張牌：過去/現在/未來，預設）
• `diamond`（鑽石牌陣：核心、阻力、潛力與建議）
• `moon`（月亮牌陣：心理與情境變化）
• `horseshoe`（馬蹄鐵牌陣：深入問題分析）
• `celtic`（塞爾特十字：全方位深度解析）"""

YINYUAN_HELP_TEXT = """🌸 【月老姻緣指引 / 生肖合婚】

📖 指令格式：
`/yiyu [你的問題]`（預設月老姻緣籤 fortune）
`/yiyu zodiac [出生年1] [出生年2] [問題]`（生肖合婚）

💡 使用示範：
• `/yiyu 我和對方適合在一起嗎？`（抽月老姻緣籤）
• `/yiyu 最近會有好的正緣桃花出現嗎？`
• `/yiyu zodiac 1995 1998 我們合嗎？`（生肖合婚模式）
• `/yiyu 生肖 1990 1993 性格與未來相處建議`

🔮 功能模式：
• **月老姻緣籤**（預設）：直接輸入問題，即刻求得籤詩並獲得 AI 感情指引
• **生肖合婚**（zodiac）：輸入雙方出生西元年份，測算生肖契合度與 AI 建議"""


def parse_tarot_command(text: str) -> tuple[str, str]:
    """Parse tarot arguments into (spread, question)."""
    clean_text = (text or "").strip()
    if not clean_text:
        return ("three", "")
    parts = clean_text.split(maxsplit=1)
    first_token = parts[0].lower()
    if first_token in SPREAD_ALIASES:
        spread = SPREAD_ALIASES[first_token]
        question = parts[1].strip() if len(parts) > 1 else ""
        return (spread, question)
    return ("three", clean_text)


def parse_yinyuan_command(text: str) -> tuple[str, str, int | None, int | None]:
    """Parse yinyuan arguments into (mode, question, first_year, second_year)."""
    clean_text = (text or "").strip()
    if not clean_text:
        return ("fortune", "", None, None)

    parts = clean_text.split()
    first_token = parts[0].lower()

    if first_token in ("zodiac", "生肖", "合婚", "配對"):
        years = [int(p) for p in parts[1:] if p.isdigit() and len(p) == 4]
        if len(years) >= 2:
            first_year, second_year = years[0], years[1]
            non_year_tokens = [p for p in parts[1:] if not (p.isdigit() and len(p) == 4)]
            question = " ".join(non_year_tokens).strip() or f"{first_year}年與{second_year}年生肖合婚測算"
            return ("zodiac", question, first_year, second_year)
        else:
            question = " ".join(parts[1:]).strip() or "生肖合婚測算"
            return ("zodiac", question, None, None)

    if first_token in ("fortune", "籤詩", "求籤", "籤"):
        question = " ".join(parts[1:]).strip()
        return ("fortune", question, None, None)

    # Check if user entered two 4-digit years without keyword (e.g. "1995 1998 我們合嗎")
    years = [int(p) for p in parts if p.isdigit() and len(p) == 4]
    if len(years) >= 2 and any(k in clean_text for k in ("合", "配", "配對", "結婚", "感情", "zodiac")):
        first_year, second_year = years[0], years[1]
        non_year_tokens = [p for p in parts if not (p.isdigit() and len(p) == 4)]
        question = " ".join(non_year_tokens).strip() or f"{first_year}年與{second_year}年生肖合婚測算"
        return ("zodiac", question, first_year, second_year)

    return ("fortune", clean_text, None, None)


def ask_tarot_api(
    question: str,
    spread: str = "three",
    base_url: str = QIMEN_API_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Send request to tarot-question endpoint."""
    url = f"{base_url.rstrip('/')}/api/tarot-question"
    payload = {"question": question, "spread": spread}
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def format_tarot_reply(data: dict, default_question: str = "", default_spread: str = "three") -> str:
    """Format the tarot API response into user-facing Telegram message."""
    if not data or not data.get("success", False):
        error_msg = data.get("message") or data.get("error") or "塔羅服務暫時無法回應，請稍後再試。"
        return f"❌ 塔羅占卜失敗：{error_msg}"

    question = data.get("question") or default_question
    reading = data.get("reading") or data.get("result") or {}
    spread_key = reading.get("spread") or default_spread
    spread_title = SPREAD_NAMES.get(spread_key, f"{spread_key} 牌陣")
    cards = reading.get("cards", [])
    answer = (data.get("answer") or "").strip()

    lines = [
        "🔮 【塔羅占卜 Tarot Reading】",
        f"📖 牌陣：{spread_title}",
        f"❓ 問題：{question}\n",
        "🃏 【抽牌結果】",
    ]

    for card in cards:
        pos = card.get("position", "")
        name = card.get("name", "")
        orientation = card.get("orientation", "正位")
        is_major = " ✨(大阿爾克那)" if card.get("isMajor") else ""
        lines.append(f"  • 【{pos}】：{name}（{orientation}）{is_major}".rstrip())

    lines.append(f"\n💡 【AI 深度解牌建議】\n{answer}")
    return "\n".join(lines)


def ask_yinyuan_api(
    question: str,
    mode: str = "fortune",
    first_year: int | None = None,
    second_year: int | None = None,
    base_url: str = QIMEN_API_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Send request to yinyuan-question endpoint."""
    url = f"{base_url.rstrip('/')}/api/yinyuan-question"
    payload = {"question": question, "mode": mode}
    if mode == "zodiac" and first_year and second_year:
        payload["firstYear"] = first_year
        payload["secondYear"] = second_year
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def format_yinyuan_reply(data: dict, default_question: str = "", mode: str = "fortune") -> str:
    """Format the yinyuan API response into user-facing Telegram message."""
    if not data or not data.get("success", False):
        error_msg = data.get("message") or data.get("error") or "姻緣測算服務暫時無法回應，請稍後再試。"
        return f"❌ 姻緣測算失敗：{error_msg}"

    question = data.get("question") or default_question
    result = data.get("result") or {}
    answer = (data.get("answer") or "").strip()

    if mode == "zodiac" or "first" in result:
        first = result.get("first", {})
        second = result.get("second", {})
        rel = result.get("relationship", "一般關係")
        score = result.get("score", "N/A")

        y1, z1 = first.get("year", ""), first.get("zodiac", "")
        y2, z2 = second.get("year", ""), second.get("zodiac", "")

        lines = [
            "🌸 【月老生肖合婚測算】",
            f"❓ 問題：{question}\n",
            "🎎 【生肖配對結果】",
            f"  • 第一方：{y1} 年生（生肖屬 {z1}）",
            f"  • 第二方：{y2} 年生（生肖屬 {z2}）",
            f"💫 契合關係：{rel}",
            f"📊 契合指數：{score} 分\n",
            f"💡 【AI 感情合婚指引】\n{answer}",
        ]
        return "\n".join(lines)
    else:
        stick_num = result.get("number", "")
        title = result.get("title", "")
        poem = result.get("poem", "")

        lines = [
            "🌸 【月老姻緣籤詩】",
            f"❓ 問題：{question}\n",
            f"📜 【抽得籤詩】：第 {stick_num} 籤 【{title}】",
            f"「{poem}」\n",
            f"💡 【AI 姻緣指引與解籤】\n{answer}",
        ]
        return "\n".join(lines)
