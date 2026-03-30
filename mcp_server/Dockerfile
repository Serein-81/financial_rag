FROM python:3.12-slim

WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

RUN pip install mcp uvicorn fastapi fastmcp sse-starlette pydantic python-multipart --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/

COPY app/ ./app/

RUN rm -f /etc/nginx/sites-enabled/default && \
    echo "server { \
    listen 8080; \
    location / { \
        proxy_pass http://127.0.0.1:8000; \
        proxy_set_header Host 127.0.0.1:8000; \
        proxy_set_header X-Forwarded-Host 127.0.0.1:8000; \
        proxy_set_header X-Real-IP \$remote_addr; \
        proxy_http_version 1.1; \
        proxy_set_header Connection ''; \
        proxy_buffering off; \
        proxy_cache off; \
        chunked_transfer_encoding off; \
    } \
}" > /etc/nginx/conf.d/mcp.conf

EXPOSE 8080

CMD sh -c "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 & sleep 3 && echo '✅ 终极反向代理启动！' && nginx -g 'daemon off;'"
