FROM python:3.12-slim

WORKDIR /app

# 配置阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list

RUN apt-get update && apt-get install -y nginx curl && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt 并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制应用代码
COPY app/ ./app/
COPY .env ./

# 配置 nginx 反向代理
RUN rm -f /etc/nginx/sites-enabled/default && \
    echo "server { \
    listen 8080; \
    server_name _; \
    location / { \
        proxy_pass http://127.0.0.1:8888; \
        proxy_set_header Host \$host; \
        proxy_set_header X-Real-IP \$remote_addr; \
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto \$scheme; \
        proxy_http_version 1.1; \
        proxy_set_header Connection ''; \
        proxy_buffering off; \
        proxy_cache off; \
        chunked_transfer_encoding off; \
    } \
}" > /etc/nginx/conf.d/mcp.conf

EXPOSE 8080

# 启动命令：uvicorn 监听 8888，nginx 监听 8080
CMD sh -c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8888 & sleep 2 && nginx -g 'daemon off;'"
