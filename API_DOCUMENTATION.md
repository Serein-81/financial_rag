# API 完整文档

## 📋 目录

- [认证说明](#认证说明)
- [审查 API](#审查-api)
- [知识库 API](#知识库-api)
- [文档 API](#文档-api)
- [聊天 API](#聊天-api)
- [记忆系统 API](#记忆系统-api)
- [错误码说明](#错误码说明)

---

## 认证说明

### JWT Token 认证

所有 API 请求（除了登录和注册）都需要在 Header 中携带 JWT Token：

```http
Authorization: Bearer <your_jwt_token>
X-Tenant-ID: <your_tenant_id>
```

### 获取 Token

**端点**: `POST /api/v1/auth/login`

**请求体**:
```json
{
  "username": "user@example.com",
  "password": "your_password"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "tenant_id": "tenant_123"
}
```

---

## 审查 API

### 1. 创建审查任务

**端点**: `POST /api/v1/audit/tasks`

**描述**: 创建一个新的文档审查任务

**请求体**:
```json
{
  "query": "请审查这份财务报表，重点关注收入和成本",
  "document_ids": [1, 2, 3],
  "options": {
    "enable_reflection": true,
    "max_rework_rounds": 2
  }
}
```

**响应**:
```json
{
  "task_id": "task_123",
  "status": "pending",
  "created_at": "2024-03-16T10:00:00Z",
  "estimated_duration": 120
}
```

### 2. 查询任务状态

**端点**: `GET /api/v1/audit/tasks/{task_id}`

**响应**:
```json
{
  "task_id": "task_123",
  "status": "completed",
  "progress": 100,
  "started_at": "2024-03-16T10:00:00Z",
  "completed_at": "2024-03-16T10:02:30Z",
  "duration": 150
}
```

状态值：
- `pending`: 等待处理
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 失败

### 3. 获取审查报告

**端点**: `GET /api/v1/audit/tasks/{task_id}/report`

**响应**:
```json
{
  "task_id": "task_123",
  "report": {
    "summary": "审查摘要...",
    "findings": [
      {
        "category": "financial",
        "severity": "high",
        "description": "发现问题描述",
        "recommendation": "建议措施"
      }
    ],
    "specialists": {
      "finance": {
        "conclusion": "财务专家结论",
        "confidence": 0.95
      },
      "tax": {
        "conclusion": "税务专家结论",
        "confidence": 0.92
      },
      "legal": {
        "conclusion": "法务专家结论",
        "confidence": 0.88
      }
    }
  },
  "generated_at": "2024-03-16T10:02:30Z"
}
```

### 4. 列表查询

**端点**: `GET /api/v1/audit/tasks`

**查询参数**:
- `status`: 过滤状态（可选）
- `page`: 页码（默认 1）
- `page_size`: 每页数量（默认 20）

**响应**:
```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "tasks": [
    {
      "task_id": "task_123",
      "status": "completed",
      "created_at": "2024-03-16T10:00:00Z"
    }
  ]
}
```

---

## 知识库 API

### 1. 创建知识库

**端点**: `POST /api/v1/knowledge/bases`

**请求体**:
```json
{
  "name": "财税知识库",
  "description": "包含财务和税务相关知识",
  "config": {
    "chunk_size": 500,
    "chunk_overlap": 50
  }
}
```

**响应**:
```json
{
  "id": 1,
  "name": "财税知识库",
  "description": "包含财务和税务相关知识",
  "created_at": "2024-03-16T10:00:00Z"
}
```

### 2. 上传文档

**端点**: `POST /api/v1/knowledge/bases/{kb_id}/documents`

**请求**: Multipart Form Data
- `file`: 文档文件（PDF, Word, Excel, 图片）
- `metadata`: JSON 格式的元数据（可选）

**响应**:
```json
{
  "document_id": 123,
  "filename": "report.pdf",
  "size": 1024000,
  "status": "processing",
  "uploaded_at": "2024-03-16T10:00:00Z"
}
```

### 3. 查询知识库

**端点**: `GET /api/v1/knowledge/bases/{kb_id}`

**响应**:
```json
{
  "id": 1,
  "name": "财税知识库",
  "description": "包含财务和税务相关知识",
  "document_count": 50,
  "chunk_count": 1500,
  "created_at": "2024-03-16T10:00:00Z",
  "updated_at": "2024-03-16T11:00:00Z"
}
```

### 4. 搜索知识

**端点**: `POST /api/v1/knowledge/bases/{kb_id}/search`

**请求体**:
```json
{
  "query": "企业所得税税率",
  "top_k": 5,
  "filters": {
    "doc_type": "tax"
  }
}
```

**响应**:
```json
{
  "results": [
    {
      "chunk_id": 456,
      "content": "企业所得税税率为25%...",
      "score": 0.95,
      "metadata": {
        "document_id": 123,
        "filename": "tax_guide.pdf",
        "page": 5
      }
    }
  ],
  "total": 5
}
```

---

## 文档 API

### 1. 上传文档

**端点**: `POST /api/v1/documents/upload`

**请求**: Multipart Form Data
- `file`: 文档文件
- `doc_type`: 文档类型（financial, tax, legal）
- `knowledge_base_id`: 知识库 ID（可选）

**响应**:
```json
{
  "document_id": 123,
  "filename": "report.pdf",
  "doc_type": "financial",
  "size": 1024000,
  "status": "uploaded",
  "url": "https://minio.example.com/documents/report.pdf"
}
```

### 2. 获取文档信息

**端点**: `GET /api/v1/documents/{document_id}`

**响应**:
```json
{
  "id": 123,
  "filename": "report.pdf",
  "doc_type": "financial",
  "size": 1024000,
  "status": "processed",
  "chunk_count": 30,
  "uploaded_at": "2024-03-16T10:00:00Z",
  "processed_at": "2024-03-16T10:01:00Z"
}
```

### 3. 删除文档

**端点**: `DELETE /api/v1/documents/{document_id}`

**响应**:
```json
{
  "message": "文档已删除",
  "document_id": 123
}
```

---

## 聊天 API

### 1. 发送消息

**端点**: `POST /api/v1/chat/sessions/{session_id}/messages`

**请求体**:
```json
{
  "content": "请帮我分析这份财务报表",
  "context": {
    "document_ids": [123, 456]
  }
}
```

**响应**:
```json
{
  "message_id": 789,
  "content": "根据您提供的财务报表...",
  "role": "assistant",
  "created_at": "2024-03-16T10:00:00Z",
  "metadata": {
    "sources": [
      {
        "document_id": 123,
        "chunk_id": 456,
        "relevance": 0.95
      }
    ]
  }
}
```

### 2. 创建会话

**端点**: `POST /api/v1/chat/sessions`

**请求体**:
```json
{
  "title": "财务报表分析",
  "context": {
    "knowledge_base_id": 1
  }
}
```

**响应**:
```json
{
  "session_id": "session_123",
  "title": "财务报表分析",
  "created_at": "2024-03-16T10:00:00Z"
}
```

### 3. 获取会话历史

**端点**: `GET /api/v1/chat/sessions/{session_id}/messages`

**查询参数**:
- `limit`: 消息数量限制（默认 50）
- `before`: 获取此消息 ID 之前的消息

**响应**:
```json
{
  "session_id": "session_123",
  "messages": [
    {
      "message_id": 789,
      "content": "请帮我分析这份财务报表",
      "role": "user",
      "created_at": "2024-03-16T10:00:00Z"
    },
    {
      "message_id": 790,
      "content": "根据您提供的财务报表...",
      "role": "assistant",
      "created_at": "2024-03-16T10:00:05Z"
    }
  ],
  "total": 2
}
```

---

## 记忆系统 API

### 1. 添加记忆

**端点**: `POST /api/v1/memory/add`

**请求体**:
```json
{
  "content": "用户偏好使用详细的财务分析",
  "memory_type": "semantic",
  "metadata": {
    "category": "preference"
  }
}
```

**响应**:
```json
{
  "memory_id": 123,
  "content": "用户偏好使用详细的财务分析",
  "memory_type": "semantic",
  "created_at": "2024-03-16T10:00:00Z"
}
```

### 2. 检索记忆

**端点**: `POST /api/v1/memory/retrieve`

**请求体**:
```json
{
  "query": "用户的分析偏好",
  "memory_type": "semantic",
  "top_k": 5
}
```

**响应**:
```json
{
  "memories": [
    {
      "memory_id": 123,
      "content": "用户偏好使用详细的财务分析",
      "relevance": 0.95,
      "created_at": "2024-03-16T10:00:00Z"
    }
  ],
  "total": 1
}
```

---

## 错误码说明

### HTTP 状态码

- `200 OK`: 请求成功
- `201 Created`: 资源创建成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证或 Token 无效
- `403 Forbidden`: 无权限访问
- `404 Not Found`: 资源不存在
- `422 Unprocessable Entity`: 请求格式正确但语义错误
- `500 Internal Server Error`: 服务器内部错误

### 错误响应格式

```json
{
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数 'query' 不能为空",
    "details": {
      "field": "query",
      "constraint": "required"
    }
  }
}
```

### 常见错误码

- `INVALID_PARAMETER`: 参数错误
- `AUTHENTICATION_FAILED`: 认证失败
- `PERMISSION_DENIED`: 权限不足
- `RESOURCE_NOT_FOUND`: 资源不存在
- `RATE_LIMIT_EXCEEDED`: 请求频率超限
- `INTERNAL_ERROR`: 内部错误

---

## 速率限制

- 认证端点: 10 次/分钟
- 查询端点: 100 次/分钟
- 上传端点: 20 次/分钟
- 其他端点: 60 次/分钟

超过限制时返回 `429 Too Many Requests`

---

## 在线文档

访问 Swagger UI 查看交互式 API 文档：

```
http://localhost:8000/docs
```

---

**更新时间**: 2024-03-16  
**版本**: 1.0.0
