# Dockerfile for RAG Backend with Advanced Features + OCR Support

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 🆕 安装系统依赖 + Tesseract OCR + 中文语言包
# 使用阿里云 Debian 镜像源，提高国内构建稳定性
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 验证 Tesseract 安装
RUN tesseract --version

# 🚀 核心优化 1：安装极速包管理器 uv
RUN pip install uv --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/

# 复制依赖文件
COPY requirements.txt .

# 🚀 核心优化 2：使用 uv 极速安装依赖
# --system: 告诉 uv 我们在 Docker 里，直接装在系统 Python 环境即可
# 合并了 requirements.txt 和 pillow/pytesseract 的安装，减少镜像体积
RUN uv pip install --system --no-cache -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt pillow pytesseract

# 复制应用代码
COPY . .

# 复制并设置启动脚本权限
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# 创建日志目录
RUN mkdir -p /app/logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 使用启动脚本
ENTRYPOINT ["/docker-entrypoint.sh"]