import yt_dlp
from pydub import AudioSegment
import subprocess
import json
import os
import re
import trafilatura
import uuid
import requests
from duckduckgo_search import AsyncDDGS
from PyPDF2 import PdfReader
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, CallbackQueryHandler, filters, ApplicationBuilder
from bs4 import BeautifulSoup
from telegram.helpers import escape_markdown
from pymongo import MongoClient
from datetime import datetime
from webvtt import WebVTT

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
    """
    if not enable_discord_webhook:
        print("Discord Webhook is disabled by configuration.")
        return  # 如果 Webhook 功能被禁用，直接返回
    
    if not discord_webhook_url:
        print("Discord Webhook URL is not set.")
        return
    
    try:
        data = {"content": content}
        response = requests.post(discord_webhook_url, json=data)
        response.raise_for_status()
        print("Message sent to Discord successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Failed to send message to Discord: {e}")


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

        # 添加郵件正文
        message.attach(MIMEText(summary, "plain", "utf-8"))

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


# 從環境變數中取得 OpenAI API Key
openai_api_key = os.environ.get("OPENAI_API_KEY", "YOUR_API_KEY")
telegram_token = os.environ.get("TELEGRAM_TOKEN", "xxx")
model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
lang = os.environ.get("TS_LANG", "繁體中文")
ddg_region = os.environ.get("DDG_REGION", "wt-wt")
chunk_size = int(os.environ.get("CHUNK_SIZE", 2100))
allowed_users = os.environ.get("ALLOWED_USERS", "")
use_audio_fallback = int(os.environ.get("USE_AUDIO_FALLBACK", "0"))
# 添加 GROQ API Key
groq_api_key = os.environ.get("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
# 添加 mongodb 紀錄功能
mongo_uri = os.environ.get("MONGO_URI", "")
mongo_client = MongoClient(mongo_uri)
db = mongo_client["bot_database"]
summary_collection = db["summaries"]
# 從環境變量中獲取設置，預設為 1（開啟）
show_processing = int(os.environ.get("SHOW_PROCESSING", "1"))



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

async def search_results(keywords):
    print(keywords, ddg_region)
    results = await AsyncDDGS().text(keywords, region=ddg_region, safesearch='off', max_results=6)
    return results


def summarize(text_array):
    try:
        # 將所有段落合併成一個完整的文本
        full_text = "\n".join(text_array)
        
        # 定義系統訊息，要求返回純文字且不含 Markdown 格式符號

        system_messages = [
            {
                "role": "system",
                "content": (
                    "請將以下原始影片內容總結為五個部分，**僅以純文字格式輸出，不使用 Markdown 語法或符號**，整體語言使用繁體中文，結構需清楚、有條理。五個部分之間請用分隔線區隔\n\n"
                    "⓵ 【容易懂 Easy Know】：使用簡單易懂、生活化的語言，將內容**濃縮成一段約120～200字**的說明，**適合十二歲兒童理解**。可使用比喻或簡化類比幫助理解。\n\n"
                    "⓶ 【總結 Overall Summary】：撰寫約**300字以上**的摘要，完整概括影片的**主要議題、論點與結論**，語氣務實、清楚，避免艱澀詞彙。\n\n"
                    "⓷ 【觀點 Viewpoints】：列出影片中提到的**3～7個主要觀點**，每點以條列方式呈現，並可加入簡短評論或補充說明。\n\n"
                    "⓸ 【摘要 Abstract】：列出**6～10個關鍵重點句**，每點簡短有力，前綴搭配合適的表情符號（如✅、⚠️、📌）以強調重點資訊。\n\n"
                    "⓹ 【關鍵字 Key Words】：整理出影片中的**核心關鍵字或詞組（約5～10個）**，避免使用完整句子或冗長敘述。\n\n"
                )
            }
        ]

        
        # system_messages = [
        #     {
        #         "role": "system",
        #         "content": (
        #             "請將以下原文總結為五個部分，並以純文字形式輸出，注意不要Markdown格式，以清晰的結構呈現，確保結果以繁體中文為主：\n"
        #             "⓵ 容易懂 (Easy Know)：使用淺顯易懂的語言，將內容濃縮成一段約120~200字的解釋，適合十二歲孩子理解。\n"
        #             "⓶ 總結 (Overall Summary)：撰寫約300字或更多，概括內容的主要議題與結論，語氣務實且易於理解。\n"
        #             "⓷ 觀點 (Viewpoints)：列出原文中提到的3~7個主要觀點，並適當補充對這些觀點的評論或看法，條列呈現。\n"
        #             "⓸ 摘要 (Abstract)：摘錄6到10個核心重點，簡潔有力，並適當搭配表情符號（如✅、⚠️、📌）凸顯關鍵信息。\n"
        #             "⓹ 關鍵字 (Key Words)：列出數個最重要的關鍵字，避免冗長描述。\n"

        #         )
        #     }
        # ]
        
        # 建構 prompt，直接附上整個文本
        prompt = "總結 the following text:\n" + full_text
        
        # 呼叫 GPT API 生成摘要
        summary = call_gpt_api(prompt, system_messages)

        # 加入機器人宣傳語
        summary += "\n\n✡ Oli小濃縮 Summary bot 為您濃縮重點 ✡"

        return summary
    except Exception as e:
        print(f"Error: {e}")
        return "Unknown error! Please contact the owner. ok@vip.david888.com"



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

def extract_youtube_transcript(youtube_url):
    ydl_opts = {
        'writesubtitles': True,
        'writeautomaticsub': True,
        'skip_download': True,
        'subtitleslangs': ['en','zh-Hant', 'zh-Hans', 'zh-TW', 'zh'],
        'outtmpl': '/tmp/%(id)s.%(ext)s',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            video_id = info['id']
            
            if 'subtitles' in info or 'automatic_captions' in info:
                ydl.download([youtube_url])
                
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




def retrieve_yt_transcript_from_url(youtube_url):
    try:
        subtitle_content = extract_youtube_transcript(youtube_url)
        if subtitle_content == "no transcript":
            if use_audio_fallback:
                print("No usable subtitles found. Falling back to audio transcription.")
                return audio_transcription(youtube_url)
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
        print(f"Error in retrieve_yt_transcript_from_url: {e}")
        return ["無法獲取字幕或進行音頻轉換。"]
    
def audio_transcription(youtube_url):
    try:
        # 使用 yt-dlp 下載音頻
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'/tmp/{str(uuid.uuid4())}.%(ext)s',
            'ffmpeg_location': '/usr/bin/ffmpeg',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'ffprobe_location': '/usr/bin/ffprobe',
            'cookies_from_browser': 'chrome'  # 添加這一行來指定 cookies 文件
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
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


def call_gpt_api(prompt, additional_messages=[]):
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": additional_messages + [
            {"role": "user", "content": prompt}
        ],
    }

    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=data)
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

async def handle_summarize(update, context):
     return await handle('summarize', update, context)


async def handle_file(update, context):
    return await handle('file', update, context)

# async def handle_button_click(update, context):
#     return await handle('button_click', update, context)
async def handle_button_click(update, context):
    query = update.callback_query
    await query.answer()

async def handle_yt2audio(update, context):
    chat_id = update.effective_chat.id
    user_input = update.message.text.split()

    if len(user_input) < 2:  # 檢查是否有提供 URL
        await context.bot.send_message(chat_id=chat_id, text="請提供一個 YouTube 影片的 URL。例如：/yt2audio Youtube的URL")
        return

    url = user_input[1]  # 取得 YouTube URL

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
        await context.bot.send_message(chat_id=chat_id, text="下載或傳送音頻失敗。請檢查輸入的 YouTube URL 是否正確。")
        


async def handle_yt2text(update, context):
    chat_id = update.effective_chat.id
    user_input = update.message.text.split()

    if len(user_input) < 2:
        await context.bot.send_message(chat_id=chat_id, text="請提供一個 YouTube 影片的 URL。例如：/yt2text Youtube的URL")
        return

    url = user_input[1]

    try:
        output_chunks = retrieve_yt_transcript_from_url(url)

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
        await context.bot.send_message(chat_id=chat_id, text="下載或轉換文本失敗。請檢查輸入的 YouTube URL 是否正確。")

def get_web_title(user_input):
    """
    根據用戶提供的 URL，抓取網頁內容並提取標題。
    """
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
    youtube_pattern = re.compile(r"https?://(www\.|m\.)?(youtube\.com|youtu\.be)/")
    url_pattern = re.compile(r"https?://")

    if youtube_pattern.match(user_input):
        # 如果是 YouTube 的網址，調用 YouTube 字幕處理函數
        text_array = retrieve_yt_transcript_from_url(user_input)
    elif url_pattern.match(user_input):
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
        {"command": "yt2audio", "description": "下載 YouTube 音頻"},
        {"command": "yt2text", "description": "將 YouTube 影片轉成文字"},
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
                                                text="我是江家機器人之一。版本20250415。我還活著。我會幫你自動總結為中文的內容。")
        elif action == 'help':
            help_text = """
            I can summarize text, URLs, PDFs and YouTube video for you. 
            請直接輸入 URL 或想要總結的文字或PDF，無論是何種語言，我都會幫你自動總結為繁體中文的內容。
            Here are the available commands:
            /start - Start the bot
            /help - Show this help message
            /yt2audio <YouTube URL> - Download YouTube audio
            /yt2text <YouTube URL> - Convert YouTube video to text
            
            You can also send me any text or URL to summarize.
            """
            await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_message.message_id, text=help_text)
        # 修改 handle 函數中的 summarize 部分
        elif action == 'summarize':
            try:
                user_input = update.message.text
                text_array = process_user_input(user_input)
                if text_array:
                    summary = summarize(text_array)
                    if is_url(user_input):
                        original_url = user_input
                        title = get_web_title(user_input)
                        summary_with_original = f"📌 {title}\n\n{summary}\n\n▶ {original_url}"
                    else:
                        original_url = None
                        title = "短文之摘要"  
                        summary_with_original = f"📌 \n{summary}\n"
                    
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
                        "timestamp": datetime.now()
                    }
                    summary_collection.insert_one(summary_data)
                    
                    if show_processing and processing_message:
                        await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)
                    
                    # 發送摘要到 Discord Webhook（如果啟用）
                    if enable_discord_webhook:
                        discord_message = f"🔔 新的摘要已生成：\n{summary_with_original}"
                        send_to_discord(discord_message)
                    
                    # 處理長消息，直接使用原始文本，不進行轉義
                    if len(summary_with_original) > 4000:
                        parts = [summary_with_original[i:i+4000] for i in range(0, len(summary_with_original), 4000)]
                        for part in parts:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=part
                            )
                    else:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=summary_with_original
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
            try:
                file = await update.message.document.get_file()
                file_path = f"/tmp/{file.file_id}.pdf"
                await file.download_to_drive(file_path)
                
                reader = PdfReader(file_path)
                text = ""
                total_pages = len(reader.pages)
                
                for i, page in enumerate(reader.pages):
                    text += page.extract_text() + "\n"
                    if i % 10 == 0:  # 每處理 10 頁更新一次進度
                        progress = f"正在處理 PDF：{i+1}/{total_pages} 頁"
                        if processing_message:
                            await context.bot.edit_message_text(chat_id=chat_id, message_id=processing_message.message_id, text=progress)
                        else:
                            processing_message = await context.bot.send_message(chat_id=chat_id, text=progress)

                os.remove(file_path)

                # 分批處理文本，避免一次性處理過多內容
                chunk_size = 5000  # 每次處理 5000 字符
                text_chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
                summary = ""

                for chunk in text_chunks:
                    chunk_summary = summarize([chunk])
                    summary += chunk_summary + "\n\n"

                # 轉義 Markdown 特殊字符
                escaped_summary = escape_markdown(summary, version=2)

                if processing_message:
                    await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)

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
                    await context.bot.delete_message(chat_id=chat_id, message_id=processing_message.message_id)

  

            except Exception as e:
                print(f"Error processing PDF: {e}")
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
        yt2audio_handler = CommandHandler('yt2audio', handle_yt2audio)
        yt2text_handler = CommandHandler('yt2text', handle_yt2text)
        set_my_commands(telegram_token)
        summarize_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_summarize)
        file_handler = MessageHandler(filters.Document.PDF, handle_file)
        button_click_handler = CallbackQueryHandler(handle_button_click)
        application.add_handler(file_handler)
        application.add_handler(start_handler)
        application.add_handler(help_handler)
        application.add_handler(yt2audio_handler)
        application.add_handler(yt2text_handler)
        application.add_handler(summarize_handler)
        application.add_handler(button_click_handler)
        application.run_polling()
    except Exception as e:
        print(e)

if __name__ == '__main__':
    main()