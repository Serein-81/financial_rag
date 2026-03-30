# MCP Server

财务税务远程工具服务（Model Context Protocol Server）

提供税务计算、法律匹配、财务分析、企业信息查询等工具的远程调用能力。

## 功能特性

- **税务计算工具**: 增值税、企业所得税、个人所得税
- **法律匹配工具**: 合同条款检查、法律条款匹配
- **财务分析工具**: 资产负债率、流动比率、速动比率、净利润率
- **企业信息工具**: 企业搜索、详细信息、风险评估

## 项目结构

```
mcp_server/
├── app/
│   ├── __init__.py
│   ├── main.py                      # FastAPI 入口 + SSE 端点
│   ├── config.py                    # 服务器配置
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py                 # 工具基类
│   │   ├── tax_tools.py            # 税务计算
│   │   ├── legal_tools.py          # 法律匹配
│   │   ├── financial_tools.py      # 财务计算
│   │   └── enterprise_tools.py     # 企业信息
│   └── auth/
│       ├── __init__.py
│       └── api_key.py              # API Key 验证
├── requirements.txt
├── Dockerfile
└── README.md
```

## 快速开始

### 环境要求

- Python 3.11+
- pip

### 安装

```bash
pip install -r requirements.txt
```

### 配置

设置环境变量：

```bash
export MCP_API_KEYS="your-api-key-1,your-api-key-2"
export MCP_PORT=5000
export MCP_LOG_LEVEL=INFO
```

### 运行

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 5000
```

或直接运行：

```bash
python app/main.py
```

## API 端点

### 健康检查

```
GET /health
```

### 列出工具

```
GET /tools
Authorization: Bearer <api_key>
```

### 执行工具

```
POST /tools/{tool_name}/execute
Authorization: Bearer <api_key>

Body:
{
    "arguments": {...}
}
```

### SSE 连接

```
GET /sse
Authorization: Bearer <api_key>
```

## 工具列表

| 工具名称 | 功能 |
|---------|------|
| calculate_tax_vat | 计算增值税 |
| calculate_corporate_tax | 计算企业所得税 |
| calculate_personal_tax | 计算个人所得税 |
| check_contract_essentials | 检查合同必备条款 |
| match_legal_provisions | 匹配法律条款 |
| calculate_asset_liability_ratio | 计算资产负债率 |
| calculate_current_ratio | 计算流动比率 |
| calculate_quick_ratio | 计算速动比率 |
| calculate_profit_margin | 计算净利润率 |
| search_enterprise_info | 搜索企业信息 |
| get_enterprise_detail | 获取企业详细信息 |
| assess_enterprise_risk | 企业风险评估 |

## Docker 部署

```bash
docker build -t mcp-server .
docker run -d \
  -e MCP_API_KEYS="your-api-key" \
  -e MCP_PORT=5000 \
  -p 5000:5000 \
  mcp-server
```

## 与 MCP 客户端配合使用

配合 `rag_backend/app/mcp/` 中的客户端使用：

```python
from app.mcp.client_manager import MCPClientManager

async with MCPClientManager(
    server_url="http://your-mcp-server:5000",
    api_key="your-api-key"
) as client:
    await client.connect()
    result = await client.call_tool("calculate_tax_vat", {
        "sales_amount": 100000,
        "vat_rate": 0.13,
        "tenant_id": "tenant_001"
    })
```

## License

MIT
