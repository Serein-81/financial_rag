# Dockerfile for RAG Backend with Advanced Features + OCR Support

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 🆕 安装系统依赖 + Tesseract OCR + 中文语言包
RUN apt-get update && apt-get install -y \
    curl \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libtesseract-dev \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# 验证 Tesseract 安装
RUN tesseract --version

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 🆕 确保 OCR 相关库已安装
RUN pip install --no-cache-dir pillow pytesseract

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