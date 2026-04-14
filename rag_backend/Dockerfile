# ==========================================
# 第一阶段：构建层 (Builder) - 脏活累活都在这干
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

# 安装编译必需的系统工具 (C编译器等)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装极速包管理器 uv
RUN pip install uv --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/

COPY requirements.txt .

# 创建独立虚拟环境，并极速安装所有重型依赖
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# ==========================================
# 第二阶段：运行层 (Runner) - 纯净、安全、极小巧
# ==========================================
FROM python:3.11-slim AS runner

WORKDIR /app

# 安装运行时必需的系统动态库（补齐了 OpenCV 和 OCR 需要的底层库）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-eng \
    libtesseract5 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 【核心操作】直接把第一阶段编译好的纯净依赖库搬过来！
COPY --from=builder /opt/venv /opt/venv

# 复制业务代码和启动脚本
COPY . .

# 将虚拟环境加入系统环境变量，激活 Python 环境
ENV PATH="/opt/venv/bin:$PATH"

# 赋予启动脚本执行权限
RUN mkdir -p /app/logs && chmod +x /app/docker-entrypoint.sh

# 暴露端口与健康检查
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动！
ENTRYPOINT ["/app/docker-entrypoint.sh"]