import yt_dlp
ydl_opts = {
    'cookiesfrombrowser': ('chrome', '/chrome-data/.config/google-chrome', None, None),
    'skip_download': True
}
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info("https://www.youtube.com/watch?v=SrMaJj2SF4s")
except Exception as e:
    print(e)
