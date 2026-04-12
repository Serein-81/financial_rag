# MCP 架构设计

## 概述

MCP (Model Context Protocol) 服务是本系统的远程工具服务模块，为多智能体系统提供专业领域的计算和查询能力。系统支持**本地模式**和**云端模式**两种部署方式。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              整体架构                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        本地环境 (rag_backend)                       │   │
│   │                                                                       │   │
│   │    ┌──────────────┐                                                 │   │
│   │    │  多智能体系统  │                                                 │   │
│   │    │   MultiAgent │                                                 │   │
│   │    └──────┬───────┘                                                 │   │
│   │           │                                                         │   │
│   │           ▼                                                         │   │
│   │    ┌──────────────┐     ┌──────────────────┐                       │   │
│   │    │ MCP Factory  │────▶│ MCP ClientManager │                       │   │
│   │    └──────────────┘     └─────────┬────────┘                       │   │
│   │                                     │                                 │   │
│   │                    ┌────────────────┼────────────────┐              │   │
│   │                    │                │                │              │   │
│   │                    ▼                ▼                ▼              │   │
│   │             ┌───────────┐   ┌───────────┐   ┌───────────┐          │   │
│   │             │Local Mode │   │Cloud Mode │   │Direct Mode│          │   │
│   │             │(本地调用)  │   │(云端调用)  │   │(直接调用)  │          │   │
│   │             └───────────┘   └─────┬─────┘   └───────────┘          │   │
│   │                                    │                                │   │
│   └────────────────────────────────────┼────────────────────────────────┘   │
│                                        │                                     │
│                                        │ HTTP/REST                          │
│                                        ▼                                     │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        云端环境 (mcp_server)                         │   │
│   │                                                                       │   │
│   │    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │   │
│   │    │   Nginx       │────▶│  FastAPI      │────▶│  工具层      │    │   │
│   │    │  (反向代理)    │     │  (服务入口)   │     │              │    │   │
│   │    │   端口:8080   │     │              │     │  - 税务工具   │    │   │
│   │    └──────────────┘     └──────────────┘     │  - 法律工具   │    │   │
│   │                                                │  - 财务工具   │    │   │
│   │                                                │  - 企业工具   │    │   │
│   │                                                └──────────────┘    │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. MCP Factory (mcp_factory.py)

统一的 MCP 客户端工厂，支持多种调用模式：

```python
from app.mcp import mcp_factory, MCPMode

# 获取工具（自动选择模式）
async def get_tax_calculation(params):
    result = await mcp_factory.call_tool("calculate_tax_vat", params)
    return result
```

### 2. MCP Client Manager (client_manager.py)

客户端管理器，负责维护工具注册和调用：

```python
from app.mcp import MCPClientManager, MCPToolInfo

manager = MCPClientManager()

# 获取可用工具列表
tools = await manager.list_tools()

for tool in tools:
    print(f"工具: {tool.name}, 描述: {tool.description}")
```

### 3. MCP Tool Proxy (mcp_tool_proxy.py)

工具代理，封装工具调用逻辑：

```python
from app.mcp import mcp_tool_proxy

# 调用代理
result = await mcp_tool_proxy.call("calculate_tax_vat", {
    "sales_amount": 100000,
    "vat_rate": 0.13
})
```

## 工具分类

### 税务工具 (tax_tools.py)

| 工具名称 | 功能 | 主要参数 |
|---------|------|---------|
| calculate_tax_vat | 增值税计算 | sales_amount, vat_rate, input_vat |
| calculate_corporate_tax | 企业所得税计算 | taxable_income, tax_rate, small_business |
| calculate_personal_income_tax | 个人所得税计算 | monthly_income, tax_rate |
| tax_risk_assessment | 税务风险评估 | financial_data, industry |
| invoice_validation | 发票验证 | invoice_code, invoice_number |

### 法律工具 (legal_tools.py)

| 工具名称 | 功能 | 主要参数 |
|---------|------|---------|
| law_search | 法律法规检索 | keywords, law_type |
| case_similarity_search | 案例相似度检索 | case_description |
| compliance_check | 合规检查 | business_type, scenario |

### 财务工具 (financial_tools.py)

| 工具名称 | 功能 | 主要参数 |
|---------|------|---------|
| financial_ratio_analysis | 财务比率分析 | financial_data |
| cash_flow_analysis | 现金流分析 | cash_flow_data |
| profitability_analysis | 盈利能力分析 | revenue_data, cost_data |

### 企业工具 (enterprise_tools.py)

| 工具名称 | 功能 | 主要参数 |
|---------|------|---------|
| enterprise_search | 企业信息查询 | company_name, credit_code |
| business_status_check | 经营状态检查 | company_name |
| shareholder_analysis | 股东分析 | company_name |

## 调用模式

### 1. 本地模式 (Local Mode)

直接调用本地 MCP 服务：

```bash
# .env 配置
MCP_MODE=local
LOCAL_MCP_URL=http://localhost:8081
```

```python
from app.mcp import LocalMCPClient

client = LocalMCPClient(base_url="http://localhost:8081")
result = await client.call_tool("calculate_tax_vat", params)
```

### 2. 云端模式 (Cloud Mode)

调用远程云端 MCP 服务：

```bash
# .env 配置
MCP_MODE=cloud
MCP_SERVER_URL=http://your-cloud-server:8080
MCP_API_KEY=your_api_key
```

```python
from app.mcp import CloudMCPClient

client = CloudMCPClient(
    base_url="http://your-cloud-server:8080",
    api_key="your_api_key"
)
result = await client.call_tool("calculate_tax_vat", params)
```

### 3. 直接模式 (Direct Mode)

绕过 MCP，直接调用本地实现：

```bash
# .env 配置
MCP_MODE=direct
```

```python
# 直接使用本地工具实现
from app.tools.tax_tools import VATCalculatorTool

tool = VATCalculatorTool()
result = await tool.execute(sales_amount=100000, vat_rate=0.13)
```

## 部署架构

### 本地部署

```
┌─────────────────────────────────────────────────────┐
│           本地 Docker Compose                       │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │ PostgreSQL │  │   Redis    │  │   Neo4j    │    │
│  └────────────┘  └────────────┘  └────────────┘    │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │              rag_backend (FastAPI)              │ │
│  │   - 多智能体系统                                 │ │
│  │   - MCP Client                                 │ │
│  │   - API 接口                                    │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 云端部署

```
┌─────────────────────────────────────────────────────┐
│              云端服务器                              │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │              mcp_server (Docker)               │ │
│  │   - Nginx (反向代理, 端口 8080)                   │ │
│  │   - FastAPI (服务入口)                          │ │
│  │   - 税务工具                                     │ │
│  │   - 法律工具                                     │ │
│  │   - 财务工具                                     │ │
│  │   - 企业工具                                     │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  安全组配置: 允许 8080 端口入站                      │
└─────────────────────────────────────────────────────┘
```

## 云端部署步骤

### 1. 服务器准备

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 验证安装
docker --version
docker-compose --version
```

### 2. 上传代码

```bash
# 方式一: Git 克隆
git clone https://your-repo/mcp_server.git
cd mcp_server

# 方式二: SCP 上传
scp -r ./mcp_server user@your-server:/opt/
```

### 3. 配置环境变量

```bash
# 创建 .env 文件
cat > /opt/mcp_server/.env << EOF
# 服务配置
HOST=0.0.0.0
PORT=8080
LOG_LEVEL=INFO

# API 认证
API_KEY=your_secure_api_key
ENABLE_API_KEY=true

# CORS 配置
ALLOWED_ORIGINS=http://your-frontend.com,http://localhost:5173
EOF
```

### 4. 构建和启动

```bash
cd /opt/mcp_server

# 构建镜像
docker build -t mcp-server:latest .

# 启动服务
docker run -d \
  --name mcp-server \
  -p 8080:8080 \
  --env-file .env \
  --restart unless-stopped \
  mcp-server:latest
```

### 5. 验证部署

```bash
# 检查服务状态
curl http://localhost:8080/health

# 测试工具调用
curl -X POST http://localhost:8080/api/v1/tools/call \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "tool_name": "calculate_tax_vat",
    "parameters": {
      "sales_amount": 100000,
      "vat_rate": 0.13
    }
  }'
```

## API 接口

### 工具调用

```
POST /api/v1/tools/call
```

**请求头**：
```
Content-Type: application/json
X-API-Key: your_api_key
```

**请求体**：
```json
{
  "tool_name": "calculate_tax_vat",
  "parameters": {
    "sales_amount": 100000,
    "vat_rate": 0.13,
    "input_vat": 0
  }
}
```

**响应**：
```json
{
  "success": true,
  "data": {
    "sales_amount": 100000,
    "vat_rate": 0.13,
    "tax_amount": 13000,
    "net_vat_payable": 13000,
    "risk_level": "low"
  }
}
```

### 工具列表

```
GET /api/v1/tools
```

**响应**：
```json
{
  "success": true,
  "data": {
    "tools": [
      {
        "name": "calculate_tax_vat",
        "description": "计算增值税",
        "parameters": {
          "sales_amount": "number",
          "vat_rate": "number"
        }
      }
    ]
  }
}
```

## 错误处理

### 错误码

| 错误码 | 含义 | 处理建议 |
|-------|------|---------|
| 1001 | MCP服务不可用 | 检查服务状态，尝试重连 |
| 1002 | 工具调用超时 | 增加超时时间或重试 |
| 1003 | 工具参数错误 | 检查参数格式 |
| 1004 | API Key无效 | 检查API Key配置 |
| 1005 | 工具执行失败 | 查看具体错误信息 |

### 降级策略

当 MCP 服务不可用时，系统会自动降级：

```
1. 云端模式 → 本地模式
2. 本地模式 → 直接模式
3. 直接模式 → 返回错误
```

```python
# 降级调用示例
try:
    result = await mcp_factory.call_tool(tool_name, params)
except MCPConnectionError:
    # 尝试降级到本地模式
    result = await fallback_to_local(params)
```

## 性能优化

### 并发调用

```python
import asyncio

# 并发调用多个工具
tasks = [
    mcp_factory.call_tool("tax_tool", params1),
    mcp_factory.call_tool("legal_tool", params2),
    mcp_factory.call_tool("finance_tool", params3)
]

results = await asyncio.gather(*tasks, return_exceptions=True)
```

### 缓存策略

```python
from functools import lru_cache

@lru_cache(maxsize=1000, ttl=3600)
async def cached_tool_call(tool_name: str, params_hash: str):
    return await mcp_factory.call_tool(tool_name, params)
```

## 监控与日志

### 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("mcp")
```

### 健康检查

```bash
# 检查服务健康状态
curl http://localhost:8080/health

# 响应
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600
}
```

## 扩展开发

### 添加新工具

1. 创建工具类：

```python
# app/tools/custom_tool.py
from app.tools.base import ToolBase, registry

@registry.register
class CustomTool(ToolBase):
    def __init__(self):
        super().__init__(
            name="custom_tool",
            description="自定义工具描述",
            timeout=30
        )

    async def execute(self, **params) -> dict:
        # 实现工具逻辑
        return {"result": "success"}
```

2. 注册到工厂：

```python
# app/tools/__init__.py
from .custom_tool import CustomTool

__all__ = [..., "CustomTool"]
```

3. 重启服务使配置生效。

## 相关文档

- [多智能体协作系统设计](./rag_backend/COLLABORATION_SYSTEM_DESIGN.md)
- [人类记忆系统设计](./rag_backend/app/memory_system/HUMAN_MEMORY_SYSTEM.md)
- [知识图谱使用指南](./rag_backend/知识图谱使用指南.md)
