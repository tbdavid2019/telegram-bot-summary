import yt_dlp
from pydub import AudioSegment
import subprocess
import json
import os
import re
import trafilatura
import uuid
import requests
from openai import OpenAI
from markitdown import MarkItDown
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ApplicationBuilder
from bs4 import BeautifulSoup
from telegram.helpers import escape_markdown
from pymongo import MongoClient
from datetime import datetime
import feedparser
import markdown
import jieba
import jieba.analyse

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# 從環境變數中提取 SMTP 設定
smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.environ.get("SMTP_PORT", 465))  # 預設使用 SSL
smtp_user = os.environ.get("SMTP_USER", "your_email@gmail.com")
smtp_password = os.environ.get("SMTP_PASSWORD", "your_password")
smtp_cc_emails = os.environ.get("SMTP_CC_EMAILS", "").split(",")  # 多個 CC 收件人以逗號分隔
enable_email = int(os.environ.get("ENABLE_EMAIL", 0))  # 控制是否啟用發送郵件功能，默認為 0（禁用）
# discord 設定
discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
enable_discord_webhook = int(os.environ.get("ENABLE_DISCORD_WEBHOOK", 0)) # 默認為 0（不啟用）



def send_to_discord(content):
    """
    發送訊息到 Discord Webhook
    如果內容過長，會自動上傳為 txt 文件
    """
    if not enable_discord_webhook:
        print("Discord Webhook is disabled by configuration.")
        return  # 如果 Webhook 功能被禁用，直接返回
    
    if not discord_webhook_url:
        print("Discord Webhook URL is not set.")
        return
    
    try:
        # Discord 訊息長度限制為 2000 字符
        max_length = 1900  # 留一些緩衝空間
        
        if len(content) <= max_length:
            # 內容不長，直接發送文字訊息
            data = {"content": content}
            response = requests.post(discord_webhook_url, json=data)
            response.raise_for_status()
            print("Message sent to Discord successfully.")
        else:
            # 內容過長，上傳為 txt 文件
            temp_file_path = f"/tmp/discord_summary_{uuid.uuid4()}.txt"
            
            # 創建 txt 文件
            with open(temp_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 準備上傳文件的數據
            with open(temp_file_path, 'rb') as f:
                files = {
                    'file': ('summary.txt', f, 'text/plain')
                }
                data = {
                    'content': '📄 摘要內容過長，已上傳為文件'
                }
                
                response = requests.post(discord_webhook_url, data=data, files=files)
                response.raise_for_status()
            
            # 刪除臨時文件
            os.remove(temp_file_path)
            print("File sent to Discord successfully.")
            
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message to Discord: {e}")
    except Exception as e:
        print(f"Error in send_to_discord: {e}")


def send_summary_via_email(summary, recipient_email, subject="摘要結果"):
    if not enable_email:
        print("Email sending is disabled by configuration.")
        return  # 如果禁用郵件功能，直接返回
    
    try:
        # 檢查必要的郵件設定
        if not smtp_server or not smtp_user or not smtp_password:
            print("郵件設定不完整，無法發送郵件")
            return
            
        # 設定郵件主體
        message = MIMEMultipart()
        message["From"] = smtp_user
        message["To"] = recipient_email
        
        # 只有在有抄送收件人時才添加 CC 欄位
        if smtp_cc_emails and any(smtp_cc_emails):
            message["CC"] = ", ".join(smtp_cc_emails)
            all_recipients = [recipient_email] + smtp_cc_emails
        else:
            all_recipients = [recipient_email]
            
        message["Subject"] = subject

        # 添加郵件正文 (轉為 HTML 以支援 Markdown 排版)
        html_summary = markdown.markdown(summary, extensions=['nl2br'])
        message.attach(MIMEText(html_summary, "html", "utf-8"))

        # 發送郵件
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(
                smtp_user,
                all_recipients,
                message.as_string(),
            )
        print(f"Email sent successfully to {recipient_email} and CC: {smtp_cc_emails if smtp_cc_emails else 'none'}")
    except Exception as e:
        print(f"Failed to send email: {e}")


# LLM1 設定 (主要模型)
llm_api_key = os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY"))  # 向後兼容
model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")

# LLM2 設定 (備用模型,可選)
llm2_api_key = os.environ.get("LLM2_API_KEY", "")
llm2_model = os.environ.get("LLM2_MODEL", "")
llm2_base_url = os.environ.get("LLM2_BASE_URL", "")
use_llm2 = bool(llm2_api_key and llm2_model and llm2_base_url)  # 只有三個都設定才啟用 LLM2

# Telegram 設定
telegram_token = os.environ.get("TELEGRAM_TOKEN", "xxx")
allowed_users = os.environ.get("ALLOWED_USERS", "")
show_processing = int(os.environ.get("SHOW_PROCESSING", "1"))

# 其他設定
lang = os.environ.get("TS_LANG", "繁體中文")
chunk_size = int(os.environ.get("CHUNK_SIZE", 2100))
use_audio_fallback = int(os.environ.get("USE_AUDIO_FALLBACK", "0"))

# GROQ API Key (用於 Whisper 語音轉文字)
groq_api_key = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")

# 可用的 LLM 模型列表 (由 LLM_MODEL 和 LLM2_MODEL 組成)
def get_available_models():
    models = []
    if model:
        models.append(model)
    if llm2_model and llm2_model not in models:
        models.append(llm2_model)
    return models if models else ["gpt-4o-mini"]  # 預設備用

# 解答之書 API URL
ANSWER_BOOK_API = os.environ.get("ANSWER_BOOK_API", "http://answerbook.david888.com/answersOriginal")

# 添加 mongodb 紀錄功能
mongo_uri = os.environ.get("MONGO_URI", "")
mongo_client = MongoClient(mongo_uri)
db = mongo_client["bot_database"]
summary_collection = db["summaries"]

# 語言配置
SUPPORTED_LANGUAGES = {
    'zh-TW': '繁體中文',
    'en': 'English'
}

# 繁體中文 System Prompt
SYSTEM_PROMPT_ZH = (
    "請將以下原始影片內容總結為五個部分，**請使用 Markdown 語法進行豐富的排版（例如：# 標題、**粗體**、- 清單等）**，整體語言使用繁體中文，結構需清楚、有條理。五個部分之間請用分隔線區隔。\n\n"
    "**重要提醒**：內容中可能包含創作者的業配廣告或贊助商推廣（如 VPN、訂閱服務、App 推廣、折扣碼等），請自動識別並**略過這些廣告內容**，不要納入摘要中。只總結影片的核心知識內容。\n\n"
    "### ⓵ 【容易懂 Easy Know】\n使用簡單易懂、生活化的語言，將內容**濃縮成一段約120～200字**的說明，**適合十二歲兒童理解**。可使用比喻或簡化類比幫助理解。\n\n"
    "### ⓶ 【總結 Overall Summary】\n撰寫約**300字以上**的摘要，完整概括影片的**主要議題、論點與結論**，語氣務實、清楚，避免艱澀詞彙。\n\n"
    "### ⓷ 【觀點 Viewpoints】\n列出影片中提到的**3～7個主要觀點**，每點以清單（List）方式呈現，並可加入簡短評論或補充說明。\n\n"
    "### ⓸ 【摘要 Abstract】\n列出**6～10個關鍵重點句**，每點簡短有力，作為清單項目，適當搭配合適的表情符號（如✅、⚠️、📌）以強調重點資訊。\n\n"
    "⓹ 【FAQ 測驗】：根據內容產出**三題選擇題**，每題有 A、B、C、D 四個選項，並在每題後附上正確答案及簡短解釋。題目應涵蓋內容的重要概念或關鍵知識點。\n\n"
)

# 英文 System Prompt
SYSTEM_PROMPT_EN = (
    "Please summarize the following content into five sections. **Please use Markdown syntax for rich formatting (e.g., # headers, **bold**, - lists, etc.)**. The output should be in English with a clear and well-organized structure. Separate each section with a divider line.\n\n"
    "**Important**: The content may contain sponsored advertisements or promotions from the creator (such as VPN services, subscription services, app promotions, discount codes, etc.). Please automatically identify and **skip these promotional contents** - do not include them in the summary. Only summarize the core knowledge content of the video.\n\n"
    "### ⓵ 【Easy Know】\nUse simple, accessible language to condense the content into approximately 120-200 words, suitable for a twelve-year-old to understand. Use analogies or simplified comparisons to aid comprehension.\n\n"
    "### ⓶ 【Overall Summary】\nWrite a summary of approximately 300 words or more, comprehensively covering the **main topics, arguments, and conclusions**. Use a practical and clear tone, avoiding obscure vocabulary.\n\n"
    "### ⓷ 【Viewpoints】\nList **3-7 main viewpoints** mentioned in the content. Present each point in list form, and add brief comments or supplementary explanations.\n\n"
    "### ⓸ 【Abstract】\nList **6-10 key highlight sentences** as a list. Each point should be brief and powerful, prefixed with appropriate emoji symbols (such as ✅, ⚠️, 📌) to emphasize key information.\n\n"
    "### ⓹ 【FAQ Quiz】\nGenerate **three multiple-choice questions** based on the content. Each question should have A, B, C, D options, followed by the correct answer and a brief explanation. Questions should cover important concepts or key knowledge points from the content.\n\n"
)


def split_user_input(text):
    paragraphs = text.split('\n')
    paragraphs = [paragraph.strip() for paragraph in paragraphs if paragraph.strip()]
    return paragraphs

def scrape_text_from_url(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return [], "無法下載該網頁的內容。"  # 返回兩個值：空內容和錯誤消息
        
        text = trafilatura.extract(downloaded, include_formatting=True)
        if text is None or text.strip() == "":
            return [], "提取的內容為空，可能該網站不支持解析。"  # 返回兩個值：空內容和錯誤消息
        
        text_chunks = text.split("\n")
        article_content = [chunk.strip() for chunk in text_chunks if chunk.strip()]
        
        if not article_content:
            return [], "提取的內容為空。"  # 返回兩個值：空內容和錯誤消息
        
        return article_content, None  # 返回兩個值：內容和無錯誤
    except Exception as e:
        print(f"Error: {e}")
        return [], f"抓取過程中發生錯誤：{str(e)}"  # 返回兩個值：空內容和錯誤信息


def summarize(text_array, language='zh-TW', selected_model=None):
    try:
        # 將所有段落合併成一個完整的文本
        full_text = "\n".join(text_array)
        
        # 使用 jieba 的 TextRank 演算法過濾掉無意義詞彙 (代名詞、副詞等)
        # allowPOS 指定只保留: 地名(ns), 名詞(n), 動名詞(vn), 動詞(v), 英文(eng)
        keywords = jieba.analyse.textrank(full_text, topK=5, allowPOS=('ns', 'n', 'vn', 'v', 'eng'))
        
        # 根據語言選擇對應的 system prompt
        if language == 'en':
            system_content = SYSTEM_PROMPT_EN
        else:
            system_content = SYSTEM_PROMPT_ZH
        
        system_messages = [
            {
                "role": "system",
                "content": system_content
            }
        ]
        
        # 建構 prompt，直接附上整個文本
        prompt = "總結 the following text:\n" + full_text
        
        # 呼叫 GPT API 生成摘要
        summary = call_gpt_api(prompt, system_messages, selected_model=selected_model)

        # 組合 Hashtag 字串
        if keywords:
            # 為了避免在 Telegram / Email 的 Markdown 中被當成 H1 大標題，
            # 我們在 # 前面加上零寬度空白，或用正常的文字格式，這裡我們使用普通的文字區塊格式拼接
            # Telegram HTML format won't interpret # format, but Markdown rendering in email will. 
            # 所以加上跳脫字元 \ 確保 Email markdown 轉換安全
            hashtag_str = " ".join([f"\\#{kw}" for kw in keywords])
            summary += f"\n\n{hashtag_str}"

        # 加入機器人宣傳語
        summary += "\n\n✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡"

        return summary
    except Exception as e:
        print(f"Error: {e}")
        return "Unknown error! Please contact the owner. ok@vip.david888.com"

def format_for_telegram(markdown_text):
    """
    將 Markdown 轉換成 Telegram 支援的有限 HTML 標籤
    Telegram 僅支援 <b>, <i>, <u>, <s>, <a>, <code>, <pre>, <tg-spoiler> 等
    不支援 <h1>~<h6>, <ul>, <li>, <p>, <br> 等標準 HTML
    """
    if not markdown_text:
        return markdown_text
        
    try:
        # 1. 將 Markdown 轉成完整 HTML
        html = markdown.markdown(markdown_text, extensions=['nl2br'])
        
        # 2. 使用 BeautifulSoup 進行標籤轉換與過濾
        soup = BeautifulSoup(html, 'html.parser')
        
        # 把標題 (<h1>~<h6>) 轉換為粗體並加換行
        for v in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            new_text = f"<b>{v.get_text()}</b>\n\n"
            v.replace_with(new_text)
            
        # 把清單項 (<li>) 轉換為帶有 bullet point 的文字
        for li in soup.find_all('li'):
            li.replace_with(f"• {li.get_text()}\n")
            
        # 移除 <ul> 和 <ol> 的外層包裹
        for ul in soup.find_all(['ul', 'ol']):
            ul.unwrap()
            
        # 把 <p> 轉換成帶有換行的純文字
        for p in soup.find_all('p'):
            p.replace_with(f"{p.get_text()}\n\n")
            
        # 把 <br> 替換為實際的換行符號
        for br in soup.find_all('br'):
            br.replace_with("\n")
            
        # 把 <hr> 替換為分隔線文字
        for hr in soup.find_all('hr'):
            hr.replace_with("\n----------\n")
            
        # 把 <strong> 轉換為 <b>
        for strong in soup.find_all('strong'):
            strong.name = 'b'
            
        # 把 <em> 轉換為 <i>
        for em in soup.find_all('em'):
            em.name = 'i'
            
        # 取得純文字並只保留 Telegram 允許的標籤
        final_text = str(soup)
        
        # html.parser 的 unwrap 跟 replace_with 可能會留下多餘的全形空白或疊加換行，簡單清理
        final_text = re.sub(r'\n{3,}', '\n\n', final_text)
        # unescape 避免 &amp; 等實體在 Telegram 中顯示異常（雖然 Telegram HTML mode 有些自動處理，但清乾淨比較保險）
        import html as html_lib
        final_text = html_lib.unescape(final_text)
        
        return final_text.strip()
    except Exception as e:
        print(f"Error formatting for Telegram: {e}")
        return markdown_text # 如果轉換失敗，退回原始文字



def is_supported_by_ytdlp(url):
    """
    檢測 URL 是否被 yt-dlp 支援的影片網站
    使用雙重檢測：URL 模式 + yt-dlp 檢測，避免將一般網站誤判為影片網站
    """
    # 第一層：URL 模式檢測已知的影片網站
    video_site_patterns = [
        r'youtube\.com|youtu\.be',
        r'vimeo\.com',
        r'bilibili\.com',
        r'dailymotion\.com',
        r'tiktok\.com',
        r'twitch\.tv',
        r'facebook\.com/watch|fb\.watch',
        r'instagram\.com/(p|reel|tv)',
        r'twitter\.com/.*/status|x\.com/.*/status',
        r'soundcloud\.com',
        r'spotify\.com',
        r'bandcamp\.com',
        r'ted\.com/talks',
        r'coursera\.org',
        r'khanacademy\.org',
        r'archive\.org',
        r'pocketcasts\.com/podcast',
        r'player\.soundon\.fm',
        r'podcasts\.apple\.com'
    ]
    
    # 如果 URL 不匹配任何已知的影片網站模式，直接返回 False
    url_lower = url.lower()
    if not any(re.search(pattern, url_lower) for pattern in video_site_patterns):
        print(f"URL {url} doesn't match known video site patterns")
        return False
    
    # 第二層：使用 yt-dlp 進行詳細檢測
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': './cookies.txt',
            'extractor_args': {'youtube': {'player_client': ['default,-web_safari']}},
            'force_ipv4': True,
            'geo_bypass': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 嘗試提取資訊而不下載
            info = ydl.extract_info(url, download=False)
            if info:
                # 檢查是否包含影片相關的欄位
                video_indicators = [
                    'formats',           # 影片格式列表
                    'duration',          # 影片長度
                    'view_count',        # 觀看次數
                    'like_count',        # 按讚數
                    'upload_date',       # 上傳日期
                    'uploader',          # 上傳者
                ]
                
                # 如果有 formats 欄位且不為空，很可能是影片
                if 'formats' in info and info['formats']:
                    return True
                
                # 如果有 duration 且大於 0，很可能是影片
                if 'duration' in info and info.get('duration', 0) > 0:
                    return True
                
                # 檢查是否有其他影片相關欄位
                if any(key in info for key in video_indicators):
                    return True
                
                return False
    except Exception as e:
        print(f"URL {url} not supported by yt-dlp: {e}")
        return False
    
    return False

def clean_subtitle(subtitle_content):
    # 移除 WEBVTT 標頭
    subtitle_content = re.sub(r'WEBVTT\n\n', '', subtitle_content)
    
    # 移除時間戳和位置資訊
    subtitle_content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*\n', '', subtitle_content)
    
    # 移除空行
    subtitle_content = re.sub(r'\n+', '\n', subtitle_content)
    
    # 移除行首的數字標記（如果有的話）
    subtitle_content = re.sub(r'^\d+\n', '', subtitle_content, flags=re.MULTILINE)
    
    return subtitle_content.strip()

def extract_video_transcript(video_url):
    """
    通用的影片字幕提取函數，支援所有 yt-dlp 支援的網站
    """
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'skip_download': True,
        'subtitleslangs': ['en','zh-Hant', 'zh-Hans', 'zh-TW', 'zh'],
        'outtmpl': '/tmp/%(id)s.%(ext)s',
        'cookiefile': './cookies.txt',  # 添加 cookies.txt 支援
        'extractor_args': {'youtube': {'player_client': ['default,-web_safari']}},
        'force_ipv4': True,
        'geo_bypass': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            video_id = info['id']
            
            if 'subtitles' in info or 'automatic_captions' in info:
                ydl.download([video_url])
                
                subtitle_content = None
                for lang in ['en','zh-Hant', 'zh-Hans', 'zh']:
                    subtitle_file = f"/tmp/{video_id}.{lang}.vtt"
                    if os.path.exists(subtitle_file):
                        with open(subtitle_file, 'r', encoding='utf-8') as file:
                            subtitle_content = file.read()
                        os.remove(subtitle_file)
                        print(f"Found and using {lang} subtitle.")
                        break

                if subtitle_content:
                    # 清理字幕內容
                    cleaned_content = clean_subtitle(subtitle_content)
                    return cleaned_content
                else:
                    print("No suitable subtitles found in specified languages.")
                    return "no transcript"
            else:
                print("No subtitles or automatic captions available for this video.")
                return "no transcript"
    except Exception as e:
        print(f"An error occurred: {e}")
        return "error"




def retrieve_video_transcript_from_url(video_url):
    """
    通用的影片字幕轉文字函數，支援所有 yt-dlp 支援的網站
    """
    try:
        subtitle_content = extract_video_transcript(video_url)
        if subtitle_content == "no transcript":
            if use_audio_fallback:
                print("No usable subtitles found. Falling back to audio transcription.")
                return audio_transcription(video_url)
            else:
                return ["該影片沒有可用的字幕，且音頻轉換功能未啟用。"]

        # 清理字幕內容
        cleaned_content = re.sub(r'WEBVTT\n\n', '', subtitle_content)
        cleaned_content = re.sub(r'\d+:\d+:\d+\.\d+ --> \d+:\d+:\d+\.\d+\n', '', cleaned_content)
        cleaned_content = re.sub(r'\n\n', ' ', cleaned_content)

        # 將清理後的內容分割成chunks
        output_chunks = []
        current_chunk = ""
        for word in cleaned_content.split():
            if len(current_chunk) + len(word) + 1 <= chunk_size:
                current_chunk += word + ' '
            else:
                output_chunks.append(current_chunk.strip())
                current_chunk = word + ' '

        if current_chunk:
            output_chunks.append(current_chunk.strip())

        return output_chunks

    except Exception as e:
        print(f"Error in retrieve_video_transcript_from_url: {e}")
        return ["無法獲取字幕或進行音頻轉換。"]
    
def audio_transcription(video_url):
    try:
        # 使用 yt-dlp 下載音頻
        ydl_opts = {
            'format': 'bestaudio[protocol^=http]/best',
            'outtmpl': f'/tmp/{str(uuid.uuid4())}.%(ext)s',
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffprobe_location': '/usr/bin/ffprobe',
            'cookiefile': './cookies.txt',  # 使用 cookies.txt 檔案
            'extractor_args': {'youtube': {'player_client': ['default,-web_safari']}},
            'force_ipv4': True,
            'geo_bypass': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            output_path = ydl.prepare_filename(info)

        output_path = output_path.replace(os.path.splitext(output_path)[1], ".mp3")
        audio_file = AudioSegment.from_file(output_path)

        chunk_size = 100 * 1000  # 100 秒
        chunks = [audio_file[i:i+chunk_size] for i in range(0, len(audio_file), chunk_size)]

        transcript = ""
        for i, chunk in enumerate(chunks):
            temp_file_path = f"/tmp/{str(uuid.uuid4())}.wav"
            chunk.export(temp_file_path, format="wav")

            curl_command = [
                "curl",
                "https://api.groq.com/openai/v1/audio/transcriptions",
                "-H", f"Authorization: Bearer {os.environ.get('GROQ_API_KEY', 'YOUR_GROQ_API_KEY')}",
                "-H", "Content-Type: multipart/form-data",
                "-F", f"file=@{temp_file_path}",
                "-F", "model=whisper-large-v3"
            ]

            result = subprocess.run(curl_command, capture_output=True, text=True)

            try:
                response_json = json.loads(result.stdout)
                transcript += response_json["text"]
            except KeyError as e:
                print("KeyError:", e)
                print("Response JSON:", response_json)
            except json.JSONDecodeError:
                print("Failed to decode JSON:", result.stdout)

            os.remove(temp_file_path)  # 刪除臨時音訊文件

        os.remove(output_path)  # 刪除下載的 mp3 文件

        # 將轉錄文本分割成 chunks
        output_sentences = transcript.split()
        output_chunks = []
        current_chunk = ""

        for word in output_sentences:
            if len(current_chunk) + len(word) + 1 <= chunk_size:
                current_chunk += word + ' '
            else:
                output_chunks.append(current_chunk.strip())
                current_chunk = word + ' '

        if current_chunk:
            output_chunks.append(current_chunk.strip())

        return output_chunks

    except Exception as e:
        print(f"Error in audio_transcription: {e}")
        return ["音頻轉錄失敗。"]    


def is_pocketcasts_url(url):
    """檢查是否為 Pocket Casts URL"""
    return 'pocketcasts.com/podcast' in url.lower()

def is_soundon_url(url):
    """檢查是否為 SoundOn URL"""
    return 'player.soundon.fm' in url.lower() or 'soundon.fm' in url.lower()

def is_apple_podcast_url(url):
    """檢查是否為 Apple Podcast URL"""
    return 'podcasts.apple.com' in url.lower()

def extract_rss_from_pocketcasts(url):
    """
    從 Pocket Casts 頁面提取 RSS feed URL
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # 從頁面內容中查找 RSS feed URL
        # Pocket Casts 頁面通常包含原始 RSS feed 信息
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 嘗試多種方式找到 RSS feed
        patterns = [
            r'"feedUrl"\s*:\s*"([^"]+)"',
            r'"feed_url"\s*:\s*"([^"]+)"',
            r'"rssUrl"\s*:\s*"([^"]+)"',
            r'feed[Uu]rl["\']?\s*[:=]\s*["\']([^"\',]+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response.text)
            if match:
                rss_url = match.group(1)
                # 處理可能的轉義字符
                rss_url = rss_url.replace('\\/', '/')
                print(f"Found RSS feed URL: {rss_url}")
                return rss_url
        
        print("Could not find RSS feed URL in Pocket Casts page")
        return None
        
    except Exception as e:
        print(f"Error extracting RSS from Pocket Casts: {e}")
        return None

def extract_rss_from_soundon(url):
    """
    從 SoundOn 頁面提取 RSS feed URL
    SoundOn 的 RSS feed 通常在頁面的 link 標籤中
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找 RSS feed link 標籤
        rss_link = soup.find('link', {'type': 'application/rss+xml'})
        if rss_link and rss_link.get('href'):
            rss_url = rss_link.get('href')
            print(f"Found SoundOn RSS feed URL: {rss_url}")
            return rss_url
        
        # 嘗試從 meta 標籤中查找
        meta_rss = soup.find('meta', {'property': 'og:rss'})
        if meta_rss and meta_rss.get('content'):
            rss_url = meta_rss.get('content')
            print(f"Found SoundOn RSS feed URL from meta: {rss_url}")
            return rss_url
        
        # 嘗試從頁面內容中用正則表達式查找
        patterns = [
            r'"rss"\s*:\s*"([^"]+)"',
            r'"feedUrl"\s*:\s*"([^"]+)"',
            r'https://[^"\s]+\.rss',
            r'https://feeds\.soundon\.fm/[^"\s]+',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response.text)
            if match:
                rss_url = match.group(0) if 'https://' in pattern else match.group(1)
                rss_url = rss_url.replace('\\/', '/')
                print(f"Found SoundOn RSS feed URL: {rss_url}")
                return rss_url
        
        print("Could not find RSS feed URL in SoundOn page")
        return None
        
    except Exception as e:
        print(f"Error extracting RSS from SoundOn: {e}")
        return None

def extract_rss_from_apple_podcast(url):
    """
    從 Apple Podcast 頁面提取 RSS feed URL
    Apple Podcast 需要通過 iTunes API 來獲取 RSS feed
    """
    try:
        # 從 URL 中提取 podcast ID
        # URL 格式: https://podcasts.apple.com/{country}/podcast/{name}/id{podcast_id}
        match = re.search(r'/id(\d+)', url)
        if not match:
            print("Could not extract podcast ID from Apple Podcast URL")
            return None
        
        podcast_id = match.group(1)
        print(f"Found Apple Podcast ID: {podcast_id}")
        
        # 使用 iTunes API 查詢 podcast 信息
        api_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('resultCount', 0) > 0:
            results = data.get('results', [])
            for result in results:
                if result.get('kind') == 'podcast' and result.get('feedUrl'):
                    rss_url = result.get('feedUrl')
                    print(f"Found Apple Podcast RSS feed URL: {rss_url}")
                    return rss_url
        
        print("Could not find RSS feed URL from Apple Podcast API")
        return None
        
    except Exception as e:
        print(f"Error extracting RSS from Apple Podcast: {e}")
        return None

def get_latest_podcast_episode(rss_url, max_episodes=1):
    """
    從 RSS feed 獲取最新的 podcast episode(s)
    返回 episode 標題和音頻 URL 列表
    """
    try:
        print(f"Fetching RSS feed: {rss_url}")
        feed = feedparser.parse(rss_url)
        
        if not feed.entries:
            print("No episodes found in RSS feed")
            return []
        
        episodes = []
        for entry in feed.entries[:max_episodes]:
            title = entry.get('title', 'Unknown Episode')
            
            # 尋找音頻 URL
            audio_url = None
            
            # 檢查 enclosures (常見的 podcast 音頻位置)
            if hasattr(entry, 'enclosures') and entry.enclosures:
                for enclosure in entry.enclosures:
                    if 'audio' in enclosure.get('type', ''):
                        audio_url = enclosure.get('href') or enclosure.get('url')
                        break
            
            # 檢查 links
            if not audio_url and hasattr(entry, 'links'):
                for link in entry.links:
                    if 'audio' in link.get('type', ''):
                        audio_url = link.get('href')
                        break
            
            # 檢查 media_content
            if not audio_url and hasattr(entry, 'media_content'):
                for media in entry.media_content:
                    if 'audio' in media.get('type', ''):
                        audio_url = media.get('url')
                        break
            
            if audio_url:
                episodes.append({
                    'title': title,
                    'audio_url': audio_url,
                    'description': entry.get('summary', '')
                })
                print(f"Found episode: {title}")
            else:
                print(f"No audio URL found for episode: {title}")
        
        return episodes
        
    except Exception as e:
        print(f"Error parsing RSS feed: {e}")
        return []

def download_and_transcribe_podcast(audio_url):
    """
    下載 podcast 音頻並使用 Whisper 轉錄
    """
    try:
        print(f"Downloading podcast audio from: {audio_url}")
        
        # 下載音頻文件
        temp_audio_path = f"/tmp/{str(uuid.uuid4())}.mp3"
        response = requests.get(audio_url, stream=True, timeout=300)
        response.raise_for_status()
        
        with open(temp_audio_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"Audio downloaded to {temp_audio_path}")
        
        # 載入音頻文件
        audio_file = AudioSegment.from_file(temp_audio_path)
        
        # 分割成較小的塊進行轉錄(100秒一塊)
        chunk_duration = 100 * 1000  # 毫秒
        chunks = [audio_file[i:i+chunk_duration] for i in range(0, len(audio_file), chunk_duration)]
        
        print(f"Audio split into {len(chunks)} chunks for transcription")
        
        transcript = ""
        for i, chunk in enumerate(chunks):
            print(f"Transcribing chunk {i+1}/{len(chunks)}")
            temp_chunk_path = f"/tmp/{str(uuid.uuid4())}.wav"
            chunk.export(temp_chunk_path, format="wav")
            
            # 使用 Groq Whisper API 轉錄
            curl_command = [
                "curl",
                "https://api.groq.com/openai/v1/audio/transcriptions",
                "-H", f"Authorization: Bearer {groq_api_key}",
                "-H", "Content-Type: multipart/form-data",
                "-F", f"file=@{temp_chunk_path}",
                "-F", "model=whisper-large-v3"
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True)
            
            try:
                response_json = json.loads(result.stdout)
                transcript += response_json.get("text", "")
            except (KeyError, json.JSONDecodeError) as e:
                print(f"Error decoding transcription response: {e}")
            
            os.remove(temp_chunk_path)
        
        # 清理下載的音頻文件
        os.remove(temp_audio_path)
        
        # 將轉錄文本分割成chunks
        output_chunks = []
        current_chunk = ""
        words = transcript.split()
        
        for word in words:
            if len(current_chunk) + len(word) + 1 <= chunk_size:
                current_chunk += word + ' '
            else:
                output_chunks.append(current_chunk.strip())
                current_chunk = word + ' '
        
        if current_chunk:
            output_chunks.append(current_chunk.strip())
        
        return output_chunks
        
    except Exception as e:
        print(f"Error downloading and transcribing podcast: {e}")
        return ["Podcast 音頻轉錄失敗。"]

def process_pocketcasts_url(url):
    """
    處理 Pocket Casts URL,提取並轉錄最新的 podcast episode
    """
    try:
        # 1. 從 Pocket Casts 頁面提取 RSS feed URL
        rss_url = extract_rss_from_pocketcasts(url)
        if not rss_url:
            return ["無法從 Pocket Casts 頁面提取 RSS feed。"]
        
        # 2. 從 RSS feed 獲取最新 episode
        episodes = get_latest_podcast_episode(rss_url, max_episodes=1)
        if not episodes:
            return ["無法從 RSS feed 獲取 podcast episodes。"]
        
        episode = episodes[0]
        print(f"Processing episode: {episode['title']}")
        
        # 3. 下載並轉錄音頻
        transcript_chunks = download_and_transcribe_podcast(episode['audio_url'])
        
        return transcript_chunks
        
    except Exception as e:
        print(f"Error processing Pocket Casts URL: {e}")
        return ["處理 Pocket Casts URL 時發生錯誤。"]

def process_soundon_url(url):
    """
    處理 SoundOn URL,提取並轉錄最新的 podcast episode
    """
    try:
        # 1. 從 SoundOn 頁面提取 RSS feed URL
        rss_url = extract_rss_from_soundon(url)
        if not rss_url:
            return ["無法從 SoundOn 頁面提取 RSS feed。"]
        
        # 2. 從 RSS feed 獲取最新 episode
        episodes = get_latest_podcast_episode(rss_url, max_episodes=1)
        if not episodes:
            return ["無法從 RSS feed 獲取 podcast episodes。"]
        
        episode = episodes[0]
        print(f"Processing SoundOn episode: {episode['title']}")
        
        # 3. 下載並轉錄音頻
        transcript_chunks = download_and_transcribe_podcast(episode['audio_url'])
        
        return transcript_chunks
        
    except Exception as e:
        print(f"Error processing SoundOn URL: {e}")
        return ["處理 SoundOn URL 時發生錯誤。"]

def process_apple_podcast_url(url):
    """
    處理 Apple Podcast URL,提取並轉錄最新的 podcast episode
    """
    try:
        # 1. 從 Apple Podcast 提取 RSS feed URL
        rss_url = extract_rss_from_apple_podcast(url)
        if not rss_url:
            return ["無法從 Apple Podcast 提取 RSS feed。"]
        
        # 2. 從 RSS feed 獲取最新 episode
        episodes = get_latest_podcast_episode(rss_url, max_episodes=1)
        if not episodes:
            return ["無法從 RSS feed 獲取 podcast episodes。"]
        
        episode = episodes[0]
        print(f"Processing Apple Podcast episode: {episode['title']}")
        
        # 3. 下載並轉錄音頻
        transcript_chunks = download_and_transcribe_podcast(episode['audio_url'])
        
        return transcript_chunks
        
    except Exception as e:
        print(f"Error processing Apple Podcast URL: {e}")
        return ["處理 Apple Podcast URL 時發生錯誤。"]

def call_gpt_api(prompt, additional_messages=[], use_llm2_model=False, selected_model=None):
    """呼叫 LLM API。
    - use_llm2_model=True 且 LLM2 已配置，則使用 LLM2
    - selected_model 可指定特定模型 (用戶透過 /model 選擇)
    """
    if use_llm2_model and use_llm2:
        api_key = llm2_api_key
        api_model = llm2_model
        api_base_url = llm2_base_url
    else:
        api_key = llm_api_key
        api_model = selected_model if selected_model else model
        api_base_url = base_url
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": api_model,
        "messages": additional_messages + [
            {"role": "user", "content": prompt}
        ],
    }

    try:
        response = requests.post(f"{api_base_url}/chat/completions", headers=headers, json=data)
        response.raise_for_status()  # 如果返回非 200 的狀態碼會拋出異常
        message = response.json()["choices"][0]["message"]["content"].strip()
        return message
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return ""


async def handle_start(update, context):
    return await handle('start', update, context)

async def handle_help(update, context):
    return await handle('help', update, context)

async def handle_model(update, context):
    """處理模型切換命令"""
    return await handle('model', update, context)

async def handle_boa(update, context):
    """取回解答之書的回答"""
    return await handle('boa', update, context)

async def handle_language(update, context):
    """處理語言切換命令"""
    return await handle('language', update, context)

async def handle_clear_context(update, context):
    """清除對話歷史"""
    return await handle('clear_context', update, context)

async def handle_show_context(update, context):
    """顯示當前對話上下文"""
    return await handle('show_context', update, context)

async def handle_summarize(update, context):
     return await handle('summarize', update, context)


async def handle_file(update, context):
    return await handle('file', update, context)

# async def handle_button_click(update, context):
#     return await handle('button_click', update, context)
async def handle_button_click(update, context):
    """處理按鈕點擊事件,包括語言切換和模型選擇"""
    query = update.callback_query
    await query.answer()
    
    # 處理語言切換按鈕
    if query.data.startswith('lang_'):
        language = query.data.split('_')[1]
        context.user_data['language'] = language
        
        lang_name = SUPPORTED_LANGUAGES.get(language, language)
        await query.edit_message_text(
            text=f"✅ 語言已切換為: {lang_name}\nLanguage switched to: {lang_name}"
        )
        return
    
    # 處理模型切換按鈕
    if query.data.startswith('model_'):
        selected_model = query.data[6:]  # 去掉 'model_' 前綴
        available_models = get_available_models()
        if selected_model in available_models:
            context.user_data['selected_model'] = selected_model
            await query.edit_message_text(
                text=f"✅ 模型已切換為: {selected_model}"
            )
        else:
            await query.edit_message_text(
                text=f"❌ 模型不可用: {selected_model}"
            )
        return
    
    # 其他按鈕處理可以在這裡添加

async def handle_yt2audio(update, context):
    chat_id = update.effective_chat.id
    user_input = update.message.text.split()

    if len(user_input) < 2:  # 檢查是否有提供 URL
        await context.bot.send_message(chat_id=chat_id, text="請提供一個影片的 URL。例如：/yt2audio 影片URL")
        return

    url = user_input[1]  # 取得影片 URL

    try:
        # 生成唯一文件名稱
        temp_uuid = str(uuid.uuid4())
        output_template = f"/tmp/{temp_uuid}.%(ext)s"

        # 使用 yt-dlp 下載音頻
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,  # 直接使用這個模板來生成文件名
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffprobe_location': '/usr/bin/ffprobe',
            'cookiefile': './cookies.txt',  # 添加 cookies.txt 支援
            'extractor_args': {'youtube': {'player_client': ['default,-web_safari']}},
            'force_ipv4': True,
            'geo_bypass': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)  # 下載音頻

        # 確保獲取到的 mp3 文件名正確
        output_path = f"/tmp/{temp_uuid}.mp3"

        # 傳送音頻檔案給 Telegram user
        with open(output_path, 'rb') as audio:
            await context.bot.send_audio(chat_id=chat_id, audio=audio)

        os.remove(output_path)  # 刪除臨時檔案       

    except Exception as e:
        print(f"Error: {e}")
        await context.bot.send_message(chat_id=chat_id, text="下載或傳送音頻失敗。請檢查輸入的影片 URL 是否正確。")
        


async def handle_yt2text(update, context):
    chat_id = update.effective_chat.id
    user_input = update.message.text.split()

    if len(user_input) < 2:
        await context.bot.send_message(chat_id=chat_id, text="請提供一個影片的 URL。例如：/yt2text 影片URL")
        return

    url = user_input[1]

    try:
        output_chunks = retrieve_video_transcript_from_url(url)

        if output_chunks and output_chunks[0] in ["該影片沒有可用的字幕。", "無法獲取字幕，且音頻轉換功能未啟用。"]:
            await context.bot.send_message(chat_id=chat_id, text=output_chunks[0])
            return

        # 處理正常情況的代碼
        temp_file_path = f"/tmp/{str(uuid.uuid4())}.txt"
        with open(temp_file_path, 'w', encoding='utf-8') as file:
            for chunk in output_chunks:
                file.write(chunk + "\n")

        with open(temp_file_path, 'rb') as txt_file:
            await context.bot.send_document(chat_id=chat_id, document=txt_file, filename="transcript.txt")

        os.remove(temp_file_path)  # 刪除臨時檔案

    except Exception as e:
        print(f"Error: {e}")
        await context.bot.send_message(chat_id=chat_id, text="下載或轉換文本失敗。請檢查輸入的影片 URL 是否正確。")

def get_video_title(video_url):
    """
    使用 yt-dlp 提取影片標題，支援所有 yt-dlp 支援的網站
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': './cookies.txt',
            'extractor_args': {'youtube': {'player_client': ['default,-web_safari']}},
            'force_ipv4': True,
            'geo_bypass': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return info.get('title', '影片')
    except Exception as e:
        print(f"Error extracting video title: {e}")
        return "影片"

def get_web_title(user_input):
    """
    根據用戶提供的 URL，抓取網頁內容並提取標題。
    支援所有 yt-dlp 支援的影片網站以及一般網頁
    """
    # 首先檢查是否為 yt-dlp 支援的影片網站
    if is_supported_by_ytdlp(user_input):
        return get_video_title(user_input)
    
    try:
        # 使用 trafilatura 抓取網頁內容
        downloaded = trafilatura.fetch_url(user_input)
        if downloaded is None:
            print(f"Failed to download content from {user_input}")
            return "無法下載該網頁的內容。"  # 返回單個錯誤訊息
        
        # 使用 BeautifulSoup 解析網頁來提取標題
        soup = BeautifulSoup(downloaded, "lxml")
        title = soup.title.string if soup.title else "無法提取標題"
        return title
    
    except Exception as e:
        print(f"Error occurred while fetching title: {e}")
        return "抓取過程中發生錯誤。"  # 捕捉異常並返回錯誤訊息
    
        
def process_user_input(user_input):
    """
    處理用戶輸入的文字或網址，並返回適當的文本內容數組
    """
    url_pattern = re.compile(r"https?://")

    if url_pattern.match(user_input):
        # 檢查是否為 Pocket Casts URL
        if is_pocketcasts_url(user_input):
            # 處理 Pocket Casts podcast
            text_array = process_pocketcasts_url(user_input)
        # 檢查是否為 SoundOn URL
        elif is_soundon_url(user_input):
            # 處理 SoundOn podcast
            text_array = process_soundon_url(user_input)
        # 檢查是否為 Apple Podcast URL
        elif is_apple_podcast_url(user_input):
            # 處理 Apple Podcast
            text_array = process_apple_podcast_url(user_input)
        # 檢查是否為 yt-dlp 支援的影片網站
        elif is_supported_by_ytdlp(user_input):
            # 如果是影片網址，調用通用字幕處理函數
            text_array = retrieve_video_transcript_from_url(user_input)
        else:
            # 如果是一般的 URL，調用網頁抓取函數
            text_array, error = scrape_text_from_url(user_input)
            if error:
                return [], error
    else:
        # 處理一般的文字輸入
        text_array = split_user_input(user_input)

    return text_array

def clear_old_commands(telegram_token):
    url = f"https://api.telegram.org/bot{telegram_token}/deleteMyCommands"
    
    scopes = ["default", "all_private_chats", "all_group_chats", "all_chat_administrators"]
    
    for scope in scopes:
        data = {"scope": {"type": scope}}
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            print(f"Old commands cleared successfully for scope: {scope}")
        else:
            print(f"Failed to clear old commands for scope {scope}: {response.text}")

def set_my_commands(telegram_token):
    clear_old_commands(telegram_token)  # 清除舊的命令
    url = f"https://api.telegram.org/bot{telegram_token}/setMyCommands"
    commands = [
        {"command": "start", "description": "確認機器人是否在線"},
        {"command": "help", "description": "顯示此幫助訊息"},
        {"command": "lang", "description": "切換語言 Switch language"},
        {"command": "model", "description": "切換/列出模型 Switch/List models"},
        {"command": "boa", "description": "解答之書 Book of Answers"},
        {"command": "context", "description": "顯示對話上下文 Show context"},
        {"command": "clear", "description": "清除對話歷史 Clear history"},
        {"command": "yt2audio", "description": "下載影片音頻（支援 YouTube、Vimeo、Bilibili 等）"},
        {"command": "yt2text", "description": "將影片轉成文字（支援 YouTube、Vimeo、Bilibili 等）"},
    ]
    data = {"commands": commands}
    response = requests.post(url, json=data)

    if response.status_code == 200:
        print("Commands set successfully.")
    else:
        print(f"Failed to set commands: {response.text}")

def is_url(text):
    url_pattern = re.compile(r'https?://\S+|www\.\S+')
    return bool(url_pattern.match(text))

async def handle(action, update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if allowed_users and str(user_id) not in allowed_users.split(','):
        await context.bot.send_message(chat_id=chat_id, text="Sorry, you are not authorized to use this bot.")
        return

    processing_message = None
    if show_processing:
        processing_message = await context.bot.send_message(chat_id=chat_id, text="處理中，請稍候...")

    try:
        if action == 'start':
            await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_message.message_id,
                                                text="Oli 333 - Summary Bot。v20260117。可以幫您自動總結為繁體中文或英文的內容。")
        elif action == 'help':
            help_text = """
   I can summarize text, URLs, PDFs, video and podcast content for you. 
   請直接輸入 URL 或想要總結的文字或PDF，無論是何種語言，我都會幫你自動總結為繁體中文的內容。
   支援影片網站：YouTube、Vimeo、Bilibili、Dailymotion、TikTok、Twitch 等 1000+ 網站
   支援 Podcast：Pocket Casts、SoundOn、Apple Podcast 及各種 RSS feed podcast
   Here are the available commands:
     /start - Start the bot
     /help - Show this help message
     /lang - Switch language (切換語言)
     /model - Switch/List LLM models (切換/列出模型)
     /boa - Book of Answers 解答之書
     /context - Show current context (顯示對話上下文)
     /clear - Clear conversation history (清除對話歷史)
     /yt2audio <Video URL> - Download video audio (支援 YouTube、Vimeo、Bilibili 等)
     /yt2text <Video URL> - Convert video to text (支援 YouTube、Vimeo、Bilibili 等)    
   You can also send me any text or URL to summarize.
   After summarizing, you can ask follow-up questions about the content.
            """
            await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_message.message_id, text=help_text)
        elif action == 'language':
            # 顯示語言選擇按鈕
            current_lang = context.user_data.get('language', 'zh-TW')
            current_lang_name = SUPPORTED_LANGUAGES.get(current_lang, 'Unknown')
            
            keyboard = [
                [
                    InlineKeyboardButton("🇹🇼 繁體中文", callback_data='lang_zh-TW'),
                    InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text=f"Current language / 當前語言: {current_lang_name}\n\nPlease select a language / 請選擇語言:",
                reply_markup=reply_markup
            )
        elif action == 'clear_context':
            # 清除對話歷史
            context.user_data['conversation_history'] = None
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text="✅ 對話歷史已清除。下一次輸入將開始新的摘要。\nConversation history cleared. Next input will start a new summary."
            )
        elif action == 'show_context':
            # 顯示當前對話上下文
            history = context.user_data.get('conversation_history')
            if history:
                info_text = f"📋 當前對話上下文 / Current Context:\n\n"
                info_text += f"🔗 來源 Source: {history.get('source_url', 'N/A')}\n"
                info_text += f"📅 時間 Time: {history.get('timestamp', 'N/A')}\n"
                info_text += f"💬 問答輪數 Q&A rounds: {len(history.get('messages', []))}\n"
                info_text += f"📝 內容長度 Content length: {len(history.get('original_content', []))} paragraphs\n\n"
                info_text += "你可以繼續提問或發送新的 URL 開始新摘要。\nYou can continue asking or send a new URL to start fresh."
            else:
                info_text = "📭 目前沒有對話歷史。\nNo conversation history available."
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_message.message_id,
                text=info_text
            )
        elif action == 'model':
            # 處理模型切換命令
            args = update.message.text.split()[1:] if update.message.text else []
            current_model = context.user_data.get('selected_model', model)
            available_models = get_available_models()
            
            if args:
                # 用戶指定了模型
                requested_model = args[0].strip()
                if requested_model in available_models:
                    context.user_data['selected_model'] = requested_model
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=processing_message.message_id,
                        text=f"✅ 模型已切換至: {requested_model}"
                    )
                else:
                    models_list = "\n".join([f"  • {m}" for m in available_models])
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=processing_message.message_id,
                        text=f"❌ 模型不存在: {requested_model}\n\n📋 可用模型:\n{models_list}"
                    )
            else:
                # 列出可用模型，使用按鈕選擇
                keyboard = []
                for m in available_models:
                    marker = "✅ " if m == current_model else ""
                    keyboard.append([InlineKeyboardButton(f"{marker}{m}", callback_data=f'model_{m}')])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=processing_message.message_id,
                    text=f"🤖 當前模型: {current_model}\n\n請選擇模型:",
                    reply_markup=reply_markup
                )
        elif action == 'boa':
            # 取回解答之書的回答
            try:
                response = requests.get(ANSWER_BOOK_API, timeout=10)
                response.raise_for_status()
                data = response.json()
                answer = data.get('answer', '無法取得回答')
                
                boa_text = f"📖 解答之書 Book of Answers\n\n{answer}"
                
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=processing_message.message_id,
                    text=boa_text
                )
            except Exception as e:
                print(f"Error fetching Book of Answers: {e}")
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=processing_message.message_id,
                    text="❌ 無法取得解答之書的回答"
                )
        # 修改 handle 函數中的 summarize 部分
        elif action == 'summarize':
            try:
                user_input = update.message.text
                
                # 檢查是否為續問
                history = context.user_data.get('conversation_history')
                if history and not is_url(user_input) and len(user_input) < 500:
                    # 處理續問
                    language = context.user_data.get('language', 'zh-TW')
                    
                    # 構建對話歷史
                    messages = [
                        {"role": "system", "content": "You are a helpful assistant that answers questions about previously summarized content."}
                    ]
                    
                    # 添加原始內容
                    original_content = "\n".join(history.get('original_content', []))
                    messages.append({"role": "user", "content": f"Original content:\n{original_content[:3000]}"})  # 限制長度
                    
                    # 添加摘要
                    messages.append({"role": "assistant", "content": f"Summary:\n{history.get('summary', '')[:2000]}"})
                    
                    # 添加之前的對話
                    for msg in history.get('messages', [])[-3:]:  # 只保留最近3輪對話
                        messages.append(msg)
                    
                    # 添加當前問題
                    messages.append({"role": "user", "content": user_input})
                    
                    # 呼叫 API (使用用戶選擇的模型)
                    selected_model = context.user_data.get('selected_model', None)
                    answer = call_gpt_api(user_input, messages[:-1], selected_model=selected_model)  # messages[:-1] 因為 call_gpt_api 會自己添加最後的 user message
                    
                    # 保存對話歷史
                    history['messages'].append({"role": "user", "content": user_input})
                    history['messages'].append({"role": "assistant", "content": answer})
                    context.user_data['conversation_history'] = history
                    
                    if show_processing and processing_message:
                        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
                    
                    await context.bot.send_message(chat_id=chat_id, text=f"💬 續問回答:\n\n{answer}")
                    return
                
                # 正常的摘要流程
                text_array = process_user_input(user_input)
                if text_array:
                    # 獲取用戶語言偏好和選擇的模型
                    language = context.user_data.get('language', 'zh-TW')
                    selected_model = context.user_data.get('selected_model', None)
                    
                    summary = summarize(text_array, language=language, selected_model=selected_model)
                    if is_url(user_input):
                        original_url = user_input
                        title = get_web_title(user_input)
                        summary_with_original = f"📌 {title}\n\n{summary}\n\n▶ {original_url}"
                    else:
                        original_url = None
                        title = "短文之摘要"  
                        summary_with_original = f"📌 \n{summary}\n"
                    
                    # 保存對話歷史到 context.user_data
                    context.user_data['conversation_history'] = {
                        'original_content': text_array,
                        'summary': summary,
                        'source_url': original_url or 'text input',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'messages': [],
                        'language': language
                    }
                    
                    # 移除這一行，不需要轉義普通文本
                    # 在使用時加入條件判斷
                    if enable_email:
                        # 新增：將摘要寄送到指定郵箱
                        # 注意：需要一個主要收件人，而不僅是抄送列表
                        if smtp_user:  # 使用發件人地址作為主要收件人
                            send_summary_via_email(summary_with_original, smtp_user, subject=title)
                        else:
                            print("無法發送郵件：缺少主要收件人地址")
                    
                    # 存儲摘要資訊到 MongoDB
                    summary_data = {
                        "telegram_id": user_id,
                        "url": original_url,
                        "summary": summary_with_original,
                        "original_content": text_array,  # 新增
                        "language": language,  # 新增
                        "timestamp": datetime.now()
                    }
                    summary_collection.insert_one(summary_data)
                    
                    if show_processing and processing_message:
                        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
                    
                    # 發送摘要到 Discord Webhook（如果啟用）
                    if enable_discord_webhook:
                        discord_message = f"🔔 新的摘要已生成：\n{summary_with_original}"
                        send_to_discord(discord_message)
                    
                    # 處理長消息，將 Markdown 轉換成 Telegram 支援的 HTML
                    formatted_summary = format_for_telegram(summary_with_original)
                    
                    if len(formatted_summary) > 4000:
                        parts = [formatted_summary[i:i+4000] for i in range(0, len(formatted_summary), 4000)]
                        for part in parts:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=part,
                                parse_mode='HTML'
                            )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=formatted_summary,
                            parse_mode='HTML'
                        )
                else:
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="無法處理輸入的文本。請確保提供了有效的文本或URL。"
                    )
            except Exception as e:
                print(f"Error in summarize action: {e}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="處理您的請求時發生錯誤，請稍後再試。"
                )
        elif action == 'file':
            import traceback
            try:
                print("=== [DEBUG] handle_file 進入 ===")
                print(f"update.message.document: {update.message.document}")
                print(f"update.message.photo: {update.message.photo}")
                if update.message.document:
                    file = await update.message.document.get_file()
                    filename = update.message.document.file_name
                    ext = os.path.splitext(filename)[1] if filename else ""
                    print(f"[DEBUG] 文件模式 filename={filename}, ext={ext}")
                elif update.message.photo:
                    # 取最大解析度的圖片
                    photo = update.message.photo[-1]
                    file = await photo.get_file()
                    filename = "photo.jpg"
                    ext = ".jpg"
                    print(f"[DEBUG] 圖片模式 filename={filename}, ext={ext}")
                else:
                    print("[DEBUG] 無法取得檔案或圖片")
                    raise Exception("無法取得檔案或圖片")
                file_path = f"/tmp/{file.file_id}{ext}"
                print(f"[DEBUG] file_path={file_path}")
                await file.download_to_drive(file_path)
                print(f"[DEBUG] 檔案已下載到 {file_path}")
                
                # 判斷是否為圖片檔案
                image_exts = [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"]
                if ext.lower() in image_exts:
                    print("[DEBUG] 進入圖片摘要模式，自動選擇 llm_client")
                    if not base_url or "openai.com" in base_url:
                        from openai import OpenAI
                        client = OpenAI()
                        print("[DEBUG] 使用 openai.OpenAI() client")
                    else:
                        from litellm import openai as litellm_openai
                        client = litellm_openai.OpenAI(api_key=llm_api_key, base_url=base_url)
                        print(f"[DEBUG] 使用 litellm.openai.OpenAI client, base_url={base_url}")
                    md = MarkItDown(llm_client=client, llm_model=model)
                else:
                    print("[DEBUG] 進入文件摘要模式")
                    md = MarkItDown()
                print("[DEBUG] 開始 markitdown 轉換")
                try:
                    result = md.convert(file_path)
                    text = result.text_content
                    print(f"[DEBUG] markitdown 轉換完成，text 長度={len(text)}")
                except Exception as e:
                    import traceback
                    print(f"[ERROR] markitdown 轉換失敗: {e}")
                    traceback.print_exc()
                    raise
                # 可選：處理進度訊息，這裡簡化為一則
                progress = "正在處理檔案..."
                if processing_message:
                    await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_message.message_id, text=progress)
                else:
                    processing_message = await context.bot.send_message(chat_id=chat_id, text=progress)

                os.remove(file_path)
                print(f"[DEBUG] 已刪除暫存檔 {file_path}")

                # 直接對整個文本進行一次性摘要，不需要分塊處理
                # 因為 LLM 可以處理高達 1,000,000 個 token
                print(f"[DEBUG] 開始對整個文本進行摘要，文本長度: {len(text)} 字符")
                language = context.user_data.get('language', 'zh-TW')
                selected_model = context.user_data.get('selected_model', None)
                summary = summarize([text], language=language, selected_model=selected_model)

                # 轉義 Markdown 特殊字符
                escaped_summary = escape_markdown(summary, version=2)
                print("[DEBUG] 摘要完成，準備發送")

                if processing_message:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
                    except Exception as e:
                        print(f"[DEBUG] 刪除 processing_message 失敗: {e}")

                # 發送 PDF 摘要到 Discord Webhook（如果啟用）
                if enable_discord_webhook:
                    discord_message = f"🔔 已成功處理一份 PDF 文件，摘要內容如下：\n{summary}"
                    send_to_discord(discord_message)

                # 分批發送摘要
                if len(summary) > 4000:
                    parts = [summary[i:i+4000] for i in range(0, len(summary), 4000)]
                    for part in parts:
                        await context.bot.send_message(chat_id=chat_id, text=part)
                else:
                    await context.bot.send_message(chat_id=chat_id, text=summary)

                if processing_message:
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
                    except Exception as e:
                        print(f"[DEBUG] 刪除 processing_message 失敗: {e}")

            except Exception as e:
                print(f"[ERROR] Error processing file: {e}")
                traceback.print_exc()
                await context.bot.send_message(chat_id=chat_id, text=f"處理檔案時發生錯誤：{str(e)}，請稍後再試。")
                await context.bot.send_message(chat_id=chat_id, text=f"處理 PDF 時發生錯誤：{str(e)}，請稍後再試。")

    except Exception as e:
        if processing_message:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_message.message_id, text="發生錯誤，請稍後再試。")
        else:
            await context.bot.send_message(chat_id=chat_id, text="發生錯誤，請稍後再試。")
        print(f"Error: {e}")

def main():
    try:
        application = ApplicationBuilder().token(telegram_token).build()
        start_handler = CommandHandler('start', handle_start)
        help_handler = CommandHandler('help', handle_help)
        lang_handler = CommandHandler('lang', handle_language)
        language_handler = CommandHandler('language', handle_language)
        model_handler = CommandHandler('model', handle_model)
        boa_handler = CommandHandler('boa', handle_boa)
        clear_handler = CommandHandler('clear', handle_clear_context)
        context_handler = CommandHandler('context', handle_show_context)
        yt2audio_handler = CommandHandler('yt2audio', handle_yt2audio)
        yt2text_handler = CommandHandler('yt2text', handle_yt2text)
        set_my_commands(telegram_token)
        summarize_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_summarize)
        file_handler = MessageHandler(filters.Document.ALL, handle_file)
        file_image_handler = MessageHandler(filters.PHOTO, handle_file)
        button_click_handler = CallbackQueryHandler(handle_button_click)
        application.add_handler(file_handler)
        application.add_handler(file_image_handler)
        application.add_handler(start_handler)
        application.add_handler(help_handler)
        application.add_handler(lang_handler)
        application.add_handler(language_handler)
        application.add_handler(model_handler)
        application.add_handler(boa_handler)
        application.add_handler(clear_handler)
        application.add_handler(context_handler)
        application.add_handler(yt2audio_handler)
        application.add_handler(yt2text_handler)
        application.add_handler(summarize_handler)
        application.add_handler(button_click_handler)
        application.run_polling()
    except Exception as e:
        print(e)

if __name__ == '__main__':
    main()