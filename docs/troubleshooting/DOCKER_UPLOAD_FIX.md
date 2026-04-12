# 🔥 Docker 环境上传问题解决方案

## ⚠️ 核心问题
后端在 Docker 容器中运行，但前端请求没有到达容器！

## 🔍 诊断步骤

### 步骤 1：运行诊断脚本
```powershell
.\docker_diagnosis.ps1
```

### 步骤 2：手动检查

#### 检查容器是否运行
```bash
docker ps | grep rag_backend
```

应该看到类似输出：
```
CONTAINER ID   IMAGE          STATUS          PORTS                    NAMES
abc123def456   rag_backend    Up 2 hours      0.0.0.0:8000->8000/tcp   rag_backend
```

#### 检查端口映射
```bash
docker port rag_backend
```

应该看到：
```
8000/tcp -> 0.0.0.0:8000
```

#### 测试容器内访问
```bash
docker exec rag_backend curl -f http://localhost:8000/
```

#### 测试宿主机访问
```bash
curl http://127.0.0.1:8000/
```

### 步骤 3：如果容器未运行

```bash
cd rag_backend
docker-compose down
docker-compose up -d
docker logs -f rag_backend
```

### 步骤 4：如果容器运行但无法访问

#### 检查防火墙
```bash
# Windows
netsh advfirewall firewall show rule name="Docker"
```

#### 检查端口占用
```bash
# Windows
netstat -ano | findstr 8000
```

## 🎯 快速解决方案

### 方案 1：重启 Docker 容器（最常用）

```bash
cd rag_backend
docker-compose restart backend
docker logs -f rag_backend
```

### 方案 2：完整重建

```bash
cd rag_backend
docker-compose down
docker-compose up -d --build
docker logs -f rag_backend
```

### 方案 3：检查环境变量

```bash
docker exec rag_backend env | grep -E "POSTGRES|REDIS|MINIO"
```

确保所有必需的环境变量都已设置。

## 📊 验证修复

### 1. 确认容器正在运行
```bash
docker ps | grep rag_backend
```

### 2. 确认端口映射正确
```bash
docker port rag_backend
# 应该显示: 8000/tcp -> 0.0.0.0:8000
```

### 3. 测试健康检查
```bash
curl http://127.0.0.1:8000/
# 应该返回 HTML 或 JSON
```

### 4. 测试上传接口
```bash
# 创建测试文件
echo "%PDF-1.4 test" > test.pdf

# 测试上传（需要有效的 token）
curl -X POST "http://127.0.0.1:8000/api/v1/tax-reports/upload?tax_type=VAT" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test.pdf"

rm test.pdf
```

### 5. 检查容器日志
```bash
# 实时查看日志
docker logs -f rag_backend

# 或者查看最后 100 行
docker logs --tail 100 rag_backend
```

## 🔍 常见问题

### ❌ 容器状态为 Exit
**原因**：应用启动失败
**解决**：
```bash
docker logs rag_backend
# 查看错误信息
```

### ❌ 端口已被占用
**原因**：8000 端口被其他程序占用
**解决**：
```bash
# 找到占用端口的进程
netstat -ano | findstr 8000

# 停止该进程或更改 Docker 端口映射
```

### ❌ 无法连接到数据库/Redis
**原因**：Docker 网络配置问题
**解决**：
```bash
# 检查 Docker 网络
docker network ls
docker network inspect bridge

# 重启 Docker Compose
docker-compose down
docker-compose up -d
```

### ❌ 容器内 curl 失败
**原因**：容器内没有 curl
**解决**：
```bash
# 进入容器
docker exec -it rag_backend /bin/bash

# 或者使用 wget
docker exec rag_backend wget -O- http://localhost:8000/
```

## ✅ 确认修复成功

修复后，你应该看到：

### 后端日志（Docker 容器内）
```
🏠 [8cbd5945] POST /api/v1/tax-reports/upload
📤 [TaxUpload] 收到上传请求: xxx.pdf, 大小: xxx
🚀 [TaxUpload] 快速返回: 报告ID=xxx, 总耗时: 0.15s
```

### 宿主机测试
```bash
curl http://127.0.0.1:8000/
# 应该有响应
```

### 浏览器测试
1. 打开前端应用
2. 上传文件
3. 应该成功上传

## 📞 如果仍然无法工作

1. **完全重建**：
```bash
cd rag_backend
docker-compose down -v  # 注意：这会删除数据卷
docker-compose up -d --build
```

2. **检查日志**：
```bash
docker logs rag_backend --tail 200
```

3. **获取帮助**：
```bash
# 导出容器日志
docker logs rag_backend > backend.log 2>&1

# 导出容器信息
docker inspect rag_backend > container_info.json
```
