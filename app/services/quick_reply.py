"""Quick Reply interactive options and transformation services."""

import re
import urllib.parse
try:
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
except ImportError:
    InlineKeyboardMarkup = None
    InlineKeyboardButton = None


def get_summary_quick_reply_keyboard():
    """Generate interactive quick reply inline keyboard for summaries."""
    if InlineKeyboardMarkup is None:
        return None
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 1分鐘極簡版", callback_data="quick_1min"),
            InlineKeyboardButton("📊 結構化大綱", callback_data="quick_outline"),
        ],
        [
            InlineKeyboardButton("❓ 核心 Q&A", callback_data="quick_qa"),
            InlineKeyboardButton("📱 社群貼文風", callback_data="quick_social"),
        ],
        [
            InlineKeyboardButton("🎨 繪製概念圖", callback_data="quick_image"),
            InlineKeyboardButton("📚 發布至 Wiki", callback_data="quick_wiki"),
        ]
    ])


def detect_quick_reply_intent(text: str) -> str | None:
    """Detect if user's natural text requests a specific summary transformation style."""
    t = text.strip().lower()
    
    # 1. 1分鐘極簡版
    if any(k in t for k in ["1分鐘", "一分鐘", "極簡", "精簡版", "三句話", "1 min", "quick take"]):
        return "1min"
    
    # 2. 結構化大綱
    if any(k in t for k in ["大綱", "心智圖", "結構化大綱", "階層大綱", "架構圖", "outline", "mindmap"]):
        return "outline"
        
    # 3. 核心 Q&A
    if any(k in t for k in ["q&a", "qa", "問答", "5個問答", "常見問題", "faq"]):
        return "qa"
        
    # 4. 社群貼文風
    if any(k in t for k in ["社群", "貼文", "文案", "threads", "fb", "ig", "instagram", "social post"]):
        return "social"
        
    # 5. 繪製概念圖
    if any(k in t for k in ["生圖", "畫圖", "概念圖", "畫一張", "繪製圖片", "繪製概念圖", "generate image", "draw image"]):
        return "image"
        
    # 6. 發布至 Wiki
    if any(k in t for k in ["發布到 wiki", "發布至 wiki", "存到 wiki", "wiki 好讀版", "publish to wiki"]):
        return "wiki"
        
    return None


def build_transform_prompt(action: str, content: str, language: str = "zh-TW") -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the requested transformation."""
    lang_name = "繁體中文 (Traditional Chinese)" if language == "zh-TW" else "English"
    
    if action == "1min":
        system_prompt = f"You are a concise executive summarizer. Respond in {lang_name} using markdown."
        user_prompt = (
            f"請根據以下內容，以 {lang_name} 提煉出【⚡ 1分鐘極簡版】：\n\n"
            f"1. **3 句超精華結論**（直球對決、核心 takeaway）\n"
            f"2. **關鍵數據與事實**（列出 2~3 個最重要的數字、比例或關鍵事實）\n\n"
            f"原始內容：\n{content[:4000]}"
        )
    elif action == "outline":
        system_prompt = f"You are a structured knowledge architect. Respond in {lang_name} using clear markdown."
        user_prompt = (
            f"請根據以下內容，以 {lang_name} 梳理出【📊 結構化大綱 / 階層心智圖】：\n\n"
            f"- 使用清楚的 Markdown 樹狀階層（# 章節標題、## 重點子項、- 詳細論點）\n"
            f"- 包含各章節的核心重點與論點架構，適合長影片與演講快速掌握全貌。\n\n"
            f"原始內容：\n{content[:4000]}"
        )
    elif action == "qa":
        system_prompt = f"You are an expert interviewer and educator. Respond in {lang_name} using markdown."
        user_prompt = (
            f"請根據以下內容，拆解出【❓ 5 個最具含金量的核心 Q&A】：\n\n"
            f"- 每題以 **Q1~Q5** 標註，題目精準聚焦受眾最關心的核心痛點與技術/觀點關鍵\n"
            f"- 每個回答以 **A1~A5** 回應，精煉直接、切中核心論據。\n\n"
            f"原始內容：\n{content[:4000]}"
        )
    elif action == "social":
        system_prompt = f"You are a top-tier viral social media copywriter. Respond in {lang_name} using markdown."
        user_prompt = (
            f"請將以下內容改寫為【📱 高傳播力社群貼文風】（適合 Threads / Facebook / IG）：\n\n"
            f"1. **吸睛 Hook 開頭**（一句話引發好奇與共鳴）\n"
            f"2. **精華重點條列**（適當搭配精美 Emoji 如 💡、🔥、🚀）\n"
            f"3. **痛點引導與金句結尾**\n"
            f"4. **熱門 Hashtags**（5 個繁體中文標籤）\n\n"
            f"原始內容：\n{content[:4000]}"
        )
    else:
        system_prompt = f"You are a helpful assistant. Respond in {lang_name}."
        user_prompt = content
        
    return system_prompt, user_prompt


def build_concept_image_url(prompt_text: str) -> str:
    """Generate Pollinations Flux AI image URL for concept art visualization."""
    safe_prompt = urllib.parse.quote(prompt_text.strip())
    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&model=flux"
