FROM python:3.14-slim
#FROM debian:11-slim

# 安裝必要的工具和依賴，包括 Python 3、ffmpeg 和 curl
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes \
    gcc ffmpeg curl libxml2-dev libxslt-dev zlib1g-dev unzip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Deno
RUN curl -fsSL https://deno.land/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/deno && \
    chmod +x /usr/local/bin/deno

# 升級 pip 並安裝 Python 依賴
RUN python3 -m pip install --upgrade pip setuptools wheel

# 複製 requirements.txt 到容器中
COPY requirements.txt /app/requirements.txt

# 安裝 Python 依賴
RUN pip3 install --disable-pip-version-check -r /app/requirements.txt
RUN python3 -m pip install -U --pre "yt-dlp[default]"
RUN python3 -c "import yt_dlp"
RUN python3 -c "from magika import Magika; m = Magika(); print('Magika initialized successfully')"

WORKDIR /app

# 複製應用程式 package 到容器 (cookies.txt 改由執行期 volume 掛載，不打包進映像)
COPY app /app/app

# 設置環境變量以明確指定 ffmpeg 的位置
ENV PATH="/usr/bin:${PATH}"

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python3 -c "import os, urllib.request; p = os.environ.get('API_PORT', '8001'); urllib.request.urlopen(f'http://127.0.0.1:{p}/health', timeout=3)" || exit 1

ENTRYPOINT ["python3", "-u", "-m", "app.main"]
