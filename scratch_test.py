import yt_dlp
ydl_opts = {
    'writesubtitles': True,
    'writeautomaticsub': True,
    'skip_download': True,
    'subtitleslangs': ['en','zh-Hant', 'zh-Hans', 'zh-TW', 'zh'],
    'outtmpl': '/tmp/%(id)s.%(ext)s',
    'cookiesfrombrowser': ('chrome', '/chrome-data/.config/google-chrome', None, None),
    'extractor_args': {'youtube': {'player_client': ['default,-web_safari']}},
    'force_ipv4': True,
    'geo_bypass': True,
}
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(["https://youtu.be/RzIVsmmYb3w"])
except Exception as e:
    print(f"An error occurred: {e}")
