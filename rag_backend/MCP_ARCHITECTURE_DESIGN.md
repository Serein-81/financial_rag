# MCP 架构设计方案

## 1. 设计概述

### 1.1 架构目标

- **SSE长连接**: 建立一次连接，复用所有工具调用
- **进门鉴权**: 仅在连接建立时携带API Key，后续调用无需重复鉴权
- **本地优先**: RAG、企业内部搜索等已实现的功能保留在本地
- **云服务集成**: 仅将需要外部数据源或计算能力的工具部署到云端
- **智能超时**: 根据工具类型动态配置超时时间（asyncio.wait_for）
- **LangGraph集成**: MCP工具自动转换为LangChain @tool供大模型使用

### 1.2 核心通信模式

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   ① 建立连接 (一次性)              ② 工具调用 (复用连接)                        │
│   ┌─────────────────┐              ┌─────────────────┐                    │
│   │ GET /sse         │              │ session.call_    │                    │
│   │ Authorization:  │              │   tool()        │                    │
│   │   Bearer <KEY>  │──────────────│ (JSON-RPC)      │                    │
│   └────────┬────────┘              └────────┬────────┘                    │
│            │                                │                              │
│            ▼                                │                              │
│   ┌─────────────────┐                       │                              │
│   │ 返回 session_id │                       │                              │
│   │ 保持 SSE 连接   │◄──────────────────────┘                              │
│   └─────────────────┘         后续所有调用通过该连接                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 连接架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         云服务器 (Container Host)                          │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                         Nginx (端口: 443)                             │  │
│   │            鉴权: 检查 SSE 握手请求中的 Bearer Token                    │  │
│   └────────────────────────────────┬────────────────────────────────────┘  │
│                                    │                                          │
│                                    ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    MCP Gateway (FastMCP)                            │  │
│   │                                                                      │  │
│   │   @mcp.tool()  ←── 自动完成工具路由分发                               │  │
│   │                                                                      │  │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │  │
│   │   │   Finance   │  │     Tax      │  │    Legal    │               │  │
│   │   │    Tools    │  │     Tools    │  │    Tools    │               │  │
│   │   │  (FastMCP)  │  │   (FastMCP)  │  │   (FastMCP)  │               │  │
│   │   └──────────────┘  └──────────────┘  └──────────────┘               │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    SSE长连接 (HTTPS) ← 鉴权仅在此处发生
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RAG Backend (MCP Client)                             │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │                    MCPClientManager                                   │ │
│   │   - async with 生命周期管理                                            │ │
│   │   - asyncio.wait_for() 动态超时                                        │ │
│   │   - MCP Session 复用                                                   │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│          ┌─────────────────────────┼─────────────────────────┐            │
│          │                         │                         │            │
│          ▼                         ▼                         ▼            │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐      │
│   │ Receptionist │         │    Intent    │         │  Specialist  │      │
│   │    Agent     │         │    Agent     │         │    Agents    │      │
│   │             │         │              │         │              │      │
│   │ 本地 RAG ✓  │         │              │         │  Finance ✓  │      │
│   │ 搜索 ✓     │         │              │         │  Tax ✓      │      │
│   └──────────────┘         └──────────────┘         │  Legal ✓    │      │
│                                                     └──────────────┘      │
│   本地实现:                                                 云端实现:      │
│   - RAG 检索        ──────────────────────────>     - 财务计算          │
│   - 企业搜索        ──────────────────────────>     - 税务计算          │
│   - 工具管理        ──────────────────────────>     - 法律匹配          │
│   - 对话管理        ──────────────────────────>     - 发票验证          │
│                                                     - 报告导出          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. MCP 工具分类

### 2.1 本地实现工具 (Local Tools)

**说明**: 这些工具已在 `app/multi_agent_system/` 中实现，不需要通过 MCP 调用

| 工具名 | 所在模块 | 功能 | Agent 使用 |
|--------|----------|------|------------|
| `rag_retriever` | rag_retriever.py | RAG 知识检索 | Receptionist, Finance, Tax, Legal |
| `enterprise_search` | search_service.py | 企业内部搜索 | Receptionist |
| `document_retriever` | tools/document_retrieval.py | 文档检索 | Receptionist, Legal |
| `intent_classifier` | intent_agent.py | 意图分类 | Intent |
| `entity_extractor` | intent_agent.py | 实体提取 | Intent |
| `specialist_router` | orchestrator.py | 专家路由 | Intent |
| `result_aggregator` | result_merger.py | 结果聚合 | Report |
| `conflict_detector` | conflict_detector.py | 冲突检测 | Reflection |
| `evidence_validator` | evidence_validator.py | 事实验证 | Reflection |
| `quality_scorer` | reflection_specialist.py | 质量评分 | Reflection |
| `improvement_suggester` | reflection_specialist.py | 改进建议 | Reflection |
| `structured_validator` | structured_output_validator.py | 结构验证 | Reflection |
| `message_bus` | message_bus.py | 消息总线 | All |

---

### 2.2 云端 MCP 工具 (Cloud MCP Tools)

**说明**: 这些工具需要外部数据源或计算能力，部署在云端容器中

#### 2.2.1 Finance MCP Tools

| 工具名 | 功能 | 输入参数 | 输出 | 超时类型 | 优先级 |
|--------|------|----------|------|----------|--------|
| `calculate_financial_ratio` | 财务比率计算 | `data`, `ratio_type` | `Result` | Calc (10s) | P0 |
| `analyze_cashflow` | 现金流分析 | `cashflow_data`, `period` | `AnalysisReport` | Calc (10s) | P0 |
| `forecast_financial` | 财务预测 | `historical_data`, `method` | `ForecastResult` | LLM (60s) | P1 |
| `compare_industry` | 行业对比 | `company_data`, `industry` | `ComparisonReport` | LLM (60s) | P1 |
| `detect_anomaly` | 异常检测 | `financial_data`, `threshold` | `AnomalyList` | Calc (10s) | P1 |
| `generate_financial_report` | 生成财务报表 | `data`, `report_type` | `FinancialReport` | LLM (60s) | P0 |

#### 2.2.2 Tax MCP Tools

| 工具名 | 功能 | 输入参数 | 输出 | 超时类型 | 优先级 |
|--------|------|----------|------|----------|--------|
| `calculate_tax` | 税务计算 | `income`, `tax_type`, `region` | `TaxResult` | Calc (10s) | P0 |
| `retrieve_tax_rules` | 税法检索 | `query`, `tax_type`, `year` | `RuleList` | LLM (60s) | P0 |
| `check_tax_benefit` | 优惠政策检查 | `scenario`, `region` | `BenefitList` | Calc (10s) | P0 |
| `validate_invoice` | 发票验证 | `invoice_data` | `ValidationResult` | Calc (10s) | P0 |
| `analyze_tax_burden` | 税负分析 | `financial_data`, `period` | `BurdenReport` | LLM (60s) | P1 |
| `generate_filing_guide` | 申报指南 | `tax_type`, `period`, `region` | `FilingGuide` | DocGen (120s) | P1 |
| `check_deduction` | 扣除项检查 | `items`, `tax_type` | `DeductionResult` | Calc (10s) | P1 |

#### 2.2.3 Legal MCP Tools

| 工具名 | 功能 | 输入参数 | 输出 | 超时类型 | 优先级 |
|--------|------|----------|------|----------|--------|
| `match_legal_reference` | 法规匹配 | `fact_pattern`, `legal_area` | `ReferenceList` | LLM (60s) | P0 |
| `analyze_contract` | 合同分析 | `contract_text` | `AnalysisResult` | LLM (60s) | P0 |
| `detect_legal_risk` | 法律风险检测 | `document`, `risk_types` | `RiskReport` | LLM (60s) | P0 |
| `check_compliance` | 合规检查 | `check_items`, `evidence` | `ComplianceResult` | LLM (60s) | P0 |
| `retrieve_clause` | 条款检索 | `clause_type`, `context` | `ClauseList` | LLM (60s) | P1 |
| `analyze_rights` | 权利义务分析 | `contract_text` | `RightsAnalysis` | LLM (60s) | P1 |
| `search_case` | 案例检索 | `case_facts`, `legal_basis` | `CaseList` | LLM (60s) | P2 |

#### 2.2.4 Report MCP Tools

| 工具名 | 功能 | 输入参数 | 输出 | 超时类型 | 优先级 |
|--------|------|----------|------|----------|--------|
| `render_template` | 模板渲染 | `template_type`, `data` | `RenderedContent` | DocGen (120s) | P0 |
| `export_pdf` | PDF 导出 | `content`, `options` | `FilePath` | DocGen (120s) | P1 |
| `export_docx` | Word 导出 | `content`, `options` | `FilePath` | DocGen (120s) | P1 |
| `export_xlsx` | Excel 导出 | `data`, `sheet_name` | `FilePath` | DocGen (120s) | P2 |
| `generate_chart` | 图表生成 | `data`, `chart_type` | `ChartData` | DocGen (120s) | P1 |
| `assemble_document` | 文档组装 | `sections`, `template` | `Document` | DocGen (120s) | P0 |

---

## 3. MCP Gateway 设计 (FastMCP)

### 3.1 架构说明

**重要**: 不使用 FastAPI 手动编写路由。FastMCP 的 `@mcp.tool()` 装饰器在底层自动完成：
- 工具注册与发现
- 请求路由分发
- 参数验证
- 响应序列化

### 3.2 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      MCP Gateway (FastMCP)                      │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                    @mcp.tool()                           │  │
│   │              自动完成工具路由与分发                         │  │
│   └──────────────────────────────────────────────────────────┘  │
│                            │                                      │
│   ┌─────────────────────────┼─────────────────────────┐          │
│   │                         │                         │          │
│   ▼                         ▼                         ▼          │
│ ┌─────────┐          ┌─────────┐          ┌─────────┐          │
│ │ Finance │          │   Tax   │          │  Legal  │          │
│ │  Tools │          │  Tools  │          │  Tools  │          │
│ └─────────┘          └─────────┘          └─────────┘          │
│                                                                  │
│   MCP SSE Endpoint: http://cloud-server:5000/mcp              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 FastMCP 实现示例

```python
# cloud_mcp_gateway/server.py
from fastmcp import FastMCP
import httpx

mcp = FastMCP("Enterprise MCP Gateway")

# Finance Tools
@mcp.tool()
async def calculate_financial_ratio(data: dict, ratio_type: str) -> dict:
    """财务比率计算"""
    ...

@mcp.tool()
async def analyze_cashflow(cashflow_data: dict, period: str) -> dict:
    """现金流分析"""
    ...

# Tax Tools
@mcp.tool()
async def calculate_tax(income: float, tax_type: str, region: str) -> dict:
    """税务计算"""
    ...

@mcp.tool()
async def retrieve_tax_rules(query: str, tax_type: str, year: int) -> dict:
    """税法检索"""
    ...

# Legal Tools
@mcp.tool()
async def match_legal_reference(fact_pattern: str, legal_area: str) -> dict:
    """法规匹配"""
    ...

# Report Tools
@mcp.tool()
async def render_template(template_type: str, data: dict) -> dict:
    """模板渲染"""
    ...

if __name__ == "__main__":
    mcp.run(transport="sse", port=5000)
```

### 3.4 健康检查端点

```python
# 健康检查不通过 MCP 协议，而是直接的 HTTP 端点
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "mcp-gateway"}
```

---

## 4. 安全机制

### 4.1 进门鉴权架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      进门鉴权架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ① SSE 握手阶段 (鉴权发生)                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Client ── GET /sse ──> Nginx                           │  │
│   │                    │                                    │  │
│   │                    ▼                                    │  │
│   │              检查 Authorization: Bearer <KEY>            │  │
│   │                    │                                    │  │
│   │              有效 ──┴──> 建立 SSE 长连接                 │  │
│   │              无效 ───> 401 Unauthorized                │  │
│   └─────────────────────────────────────────────────────────┘  │
│                          │                                    │
│                          ▼                                    │
│   ② 工具调用阶段 (无需鉴权)                                      │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  session.call_tool() ← 复用已建立的 SSE 连接              │  │
│   │                    │                                    │  │
│   │                    ▼                                    │  │
│   │              MCP Gateway 处理请求                        │  │
│   │                    │                                    │  │
│   │                    ▼                                    │  │
│   │              返回结果 (无需再次鉴权)                      │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   ✅ 优势: 简化客户端实现，减少网络开销                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Nginx 层鉴权

```nginx
# /etc/nginx/conf.d/mcp-gateway.conf

server {
    listen 443 ssl;
    server_name mcp-gateway.example.com;

    # SSL 配置
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # SSE 端点鉴权 (仅在握手时检查)
    location /sse {
        # 检查 SSE 握手请求中的 Authorization Header
        if ($http_authorization !~* "^Bearer mcp_secret_key_[A-Za-z0-9]{32}$") {
            return 401 "Unauthorized: Invalid or missing API Key";
        }

        # 转发到 MCP Gateway
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE 连接超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }

    # 消息端点 (通过 session_id 路由，无需额外鉴权)
    location /messages {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    # 健康检查端点（无需鉴权）
    location /health {
        proxy_pass http://localhost:5000/health;
        proxy_http_version 1.1;
    }
}
```

**说明**: 
- `mcp_secret_key_[A-Za-z0-9]{32}` 是正则表达式，必须完全匹配
- 32位随机字符可通过 `openssl rand -hex 16` 生成
- 健康检查端点独立于 MCP 协议，不需要鉴权
- SSE 和消息端点分离：SSE 握手鉴权，消息通过 session_id 路由

### 4.3 MCP Client 层鉴权配置

```python
# RAG Backend: app/mcp/client_manager.py

import asyncio
import logging
from contextlib import AsyncExitStack
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.types import Tool

logger = logging.getLogger(__name__)


class ToolTimeoutType(str, Enum):
    CALC = "calc"       # 计算类: 10s
    LLM = "llm"         # LLM 调用类: 60s
    DOCGEN = "docgen"   # 文档生成类: 120s


@dataclass
class MCPToolInfo:
    name: str
    description: str
    input_schema: Dict[str, Any]
    timeout_type: ToolTimeoutType


TIMEOUT_MAP: Dict[ToolTimeoutType, int] = {
    ToolTimeoutType.CALC: 10,
    ToolTimeoutType.LLM: 60,
    ToolTimeoutType.DOCGEN: 120,
}


class MCPAuthError(Exception):
    """MCP 认证错误"""
    pass


class MCPToolCallError(Exception):
    """MCP 工具调用错误"""
    pass


class MCPTimeoutError(Exception):
    """MCP 工具调用超时"""
    pass


class MCPClientManager:
    """
    MCP 客户端管理器
    
    核心特点:
    1. SSE 长连接: 初始化时建立，生命周期内复用
    2. 进门鉴权: 仅在 SSE 握手时携带 API Key
    3. JSON-RPC 调用: 通过 session.call_tool() 发起
    4. asyncio.wait_for(): 实现动态超时熔断
    """
    
    def __init__(
        self,
        server_url: str,
        api_key: str,
        timeout: int = 120,
        dynamic_timeout: bool = True
    ):
        self.server_url = server_url
        self.api_key = api_key
        self.default_timeout = timeout
        self.dynamic_timeout = dynamic_timeout

        self._session: Optional[ClientSession] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._tools: List[MCPToolInfo] = []
        self._is_initialized = False

    async def __aenter__(self) -> "MCPClientManager":
        """异步上下文管理器入口 - 建立 SSE 长连接"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口 - 安全断开连接"""
        await self.disconnect()

    async def connect(self) -> None:
        """
        建立 SSE 长连接
        
        鉴权仅在此处发生: Authorization Header 携带 API Key
        后续所有工具调用通过已建立的连接进行，无需重复鉴权
        """
        if self._is_initialized:
            logger.warning("MCP Client 已连接，跳过")
            return

        try:
            logger.info(f"正在连接 MCP Gateway: {self.server_url}")
            
            self._exit_stack = AsyncExitStack()
            
            # 建立 SSE 长连接 - 鉴权仅在此处发生
            read_stream, write_stream = await self._exit_stack.enter_async_context(
                sse_client(
                    self.server_url,
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
            )
            
            # 创建 MCP Session
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # 初始化 Session
            await self._session.initialize()
            
            # 获取可用工具列表
            tools_result = await self._session.list_tools()
            self._tools = self._convert_tools(tools_result.tools)
            
            self._is_initialized = True
            logger.info(f"✅ MCP 连接成功，发现 {len(self._tools)} 个工具")
            
        except Exception as e:
            logger.error(f"❌ MCP 连接失败: {e}")
            await self.disconnect()
            raise

    async def disconnect(self) -> None:
        """安全断开连接"""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception as e:
                logger.warning(f"断开连接时出错: {e}")
            finally:
                self._exit_stack = None
                self._session = None
                self._tools = []
                self._is_initialized = False
                logger.info("MCP 连接已断开")

    def _convert_tools(self, tools: List[Tool]) -> List[MCPToolInfo]:
        """转换 MCP 工具信息"""
        result = []
        for tool in tools:
            timeout_type = self._infer_timeout_type(tool.name)
            result.append(MCPToolInfo(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema or {},
                timeout_type=timeout_type
            ))
        return result

    def _infer_timeout_type(self, tool_name: str) -> ToolTimeoutType:
        """根据工具名推断超时类型"""
        tool_name_lower = tool_name.lower()
        
        # 计算类工具
        if any(k in tool_name_lower for k in ["calculate", "calc", "check", "validate"]):
            return ToolTimeoutType.CALC
        
        # 文档生成类工具
        if any(k in tool_name_lower for k in ["generate", "export", "render", "assemble"]):
            return ToolTimeoutType.DOCGEN
        
        # 默认 LLM 类
        return ToolTimeoutType.LLM

    def _get_timeout(self, tool_name: str) -> int:
        """根据工具名获取超时时间"""
        if not self.dynamic_timeout:
            return self.default_timeout
        
        for tool in self._tools:
            if tool.name == tool_name:
                return TIMEOUT_MAP.get(tool.timeout_type, 60)
        
        return 60

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        auto_reconnect: bool = True,
        max_retries: int = 3
    ) -> Any:
        """
        调用 MCP 工具
        
        通过 session.call_tool() 发送 JSON-RPC 请求
        使用 asyncio.wait_for() 实现动态超时
        
        ⚠️ 断线重连机制:
        - 捕获连接断开异常 (ConnectionResetError, OSError, RuntimeError)
        - 自动触发重连，对上层完全透明
        - 最大重试次数可配置，防止无限重连
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            auto_reconnect: 是否自动重连 (默认 True)
            max_retries: 最大重试次数 (默认 3)
            
        Returns:
            工具执行结果
        """
        if not self._is_initialized or not self._session:
            if auto_reconnect:
                await self.connect()
            else:
                raise MCPAuthError("MCP Client 未连接，请先调用 connect()")

        timeout = self._get_timeout(tool_name)
        retry_count = 0
        
        while retry_count <= max_retries:
            try:
                logger.info(f"调用云端工具: {tool_name} (超时: {timeout}s, 重试: {retry_count})")
                
                result = await asyncio.wait_for(
                    self._session.call_tool(tool_name, arguments),
                    timeout=timeout
                )
                
                if hasattr(result, 'content') and result.content:
                    return result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                
                return str(result)
                
            except asyncio.TimeoutError:
                logger.error(f"工具调用超时: {tool_name} (限制: {timeout}s)")
                raise MCPTimeoutError(f"工具 {tool_name} 执行超时 ({timeout}s)")
            
            except (ConnectionResetError, BrokenPipeError, OSError, RuntimeError) as e:
                """
                连接断开异常捕获 (SSE 断线常见原因):
                - Nginx proxy_read_timeout (默认 60s/300s)
                - 云端服务重启
                - 网络抖动
                """
                retry_count += 1
                logger.warning(f"⚠️ SSE 连接断开: {e} (重试 {retry_count}/{max_retries})")
                
                if retry_count > max_retries:
                    logger.error(f"❌ 重连次数超过上限，放弃调用")
                    raise MCPToolCallError(f"SSE 连接断开，重连失败: {e}")
                
                # 重连前短暂退避
                await asyncio.sleep(1 * retry_count)
                
                # 重新建立连接
                logger.info(f"🔄 正在重新建立 SSE 连接...")
                await self.disconnect()
                await self.connect()
                logger.info(f"✅ 重连成功，继续执行工具调用")
                
            except Exception as e:
                logger.error(f"工具调用失败: {tool_name} - {e}")
                raise MCPToolCallError(f"工具 {tool_name} 调用失败: {e}")

    @property
    def tools(self) -> List[MCPToolInfo]:
        """获取可用工具列表"""
        return self._tools

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._is_initialized
```

### 4.4 配置文件

```yaml
# config/mcp_config.yaml
mcp:
  gateway:
    url: "https://mcp-gateway.example.com"
    port: 5000

  security:
    api_key: "${MCP_API_KEY}"  # 环境变量注入
    header_name: "Authorization"
    header_prefix: "Bearer"

  timeout:
    default: 60           # 默认超时 60s
    max: 120              # 最大超时 120s
    by_category:
      calc: 10            # 计算类 10s
      llm: 60             # LLM 类 60s
      docgen: 120         # 文档生成 120s
```

---

## 5. MCP Client 设计 (RAG Backend)

### 5.1 客户端架构

```
┌─────────────────────────────────────────────────────────────────┐
│                  MCPClientManager                                │
│                  (async with 生命周期管理)                         │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              SSE 长连接 (AsyncExitStack)                    │ │
│  │  - 初始化时建立，生命周期内复用                               │ │
│  │  - 鉴权仅在握手时发生 (一次)                                 │ │
│  │  - 后续调用自动复用                                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              MCP Session (JSON-RPC)                        │ │
│  │  - session.call_tool() 调用工具                            │ │
│  │  - asyncio.wait_for() 超时控制                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   ToolRegistry                              │ │
│  │                                                              │ │
│  │  Local Tools:                   Cloud MCP Tools:            │ │
│  │  - rag_retriever                - calculate_financial_ratio │
│  │  - enterprise_search             - calculate_tax             │ │
│  │  - intent_classifier            - match_legal_reference     │ │
│  │  - result_aggregator            - ...                       │ │
│  │                                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                              │                                    │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    ToolRouter                               │ │
│  │                                                              │ │
│  │  1. 检查工具类型                                             │ │
│  │  2. 本地工具 → 直接调用                                      │ │
│  │  3. 云端工具 → MCP Session (复用连接)                       │ │
│  │                                                              │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 完整调用示例

```python
# app/mcp/tool_registry.py

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Callable

class ToolTimeoutType(str, Enum):
    CALC = "calc"       # 计算类: 10s
    LLM = "llm"         # LLM 调用类: 60s
    DOCGEN = "docgen"   # 文档生成类: 120s

@dataclass
class ToolConfig:
    name: str
    category: str
    timeout_type: ToolTimeoutType
    is_local: bool = False
    mcp_endpoint: str = None

TOOL_REGISTRY: Dict[str, ToolConfig] = {
    # Finance Tools
    "calculate_financial_ratio": ToolConfig(
        name="calculate_financial_ratio",
        category="finance",
        timeout_type=ToolTimeoutType.CALC,
        is_local=False,
        mcp_endpoint="calculate_financial_ratio"
    ),
    "analyze_cashflow": ToolConfig(
        name="analyze_cashflow",
        category="finance",
        timeout_type=ToolTimeoutType.CALC,
        is_local=False,
        mcp_endpoint="analyze_cashflow"
    ),
    "generate_financial_report": ToolConfig(
        name="generate_financial_report",
        category="finance",
        timeout_type=ToolTimeoutType.LLM,
        is_local=False,
        mcp_endpoint="generate_financial_report"
    ),

    # Tax Tools
    "calculate_tax": ToolConfig(
        name="calculate_tax",
        category="tax",
        timeout_type=ToolTimeoutType.CALC,
        is_local=False,
        mcp_endpoint="calculate_tax"
    ),
    "retrieve_tax_rules": ToolConfig(
        name="retrieve_tax_rules",
        category="tax",
        timeout_type=ToolTimeoutType.LLM,
        is_local=False,
        mcp_endpoint="retrieve_tax_rules"
    ),
    "generate_filing_guide": ToolConfig(
        name="generate_filing_guide",
        category="tax",
        timeout_type=ToolTimeoutType.DOCGEN,
        is_local=False,
        mcp_endpoint="generate_filing_guide"
    ),

    # Legal Tools
    "match_legal_reference": ToolConfig(
        name="match_legal_reference",
        category="legal",
        timeout_type=ToolTimeoutType.LLM,
        is_local=False,
        mcp_endpoint="match_legal_reference"
    ),
    "analyze_contract": ToolConfig(
        name="analyze_contract",
        category="legal",
        timeout_type=ToolTimeoutType.LLM,
        is_local=False,
        mcp_endpoint="analyze_contract"
    ),

    # Report Tools
    "render_template": ToolConfig(
        name="render_template",
        category="report",
        timeout_type=ToolTimeoutType.DOCGEN,
        is_local=False,
        mcp_endpoint="render_template"
    ),
    "export_pdf": ToolConfig(
        name="export_pdf",
        category="report",
        timeout_type=ToolTimeoutType.DOCGEN,
        is_local=False,
        mcp_endpoint="export_pdf"
    ),

    # Local Tools (不需要 MCP)
    "rag_retriever": ToolConfig(
        name="rag_retriever",
        category="local",
        timeout_type=ToolTimeoutType.LLM,
        is_local=True
    ),
    "enterprise_search": ToolConfig(
        name="enterprise_search",
        category="local",
        timeout_type=ToolTimeoutType.LLM,
        is_local=True
    ),
}

TIMEOUT_MAP: Dict[ToolTimeoutType, int] = {
    ToolTimeoutType.CALC: 10,
    ToolTimeoutType.LLM: 60,
    ToolTimeoutType.DOCGEN: 120,
}
```

### 5.3 完整调用示例

```python
# app/mcp/usage_example.py

import asyncio
import os
from app.mcp.client_manager import (
    MCPClientManager,
    MCPToolCallError,
    MCPTimeoutError
)


async def example():
    """MCP 客户端使用示例"""
    
    # 配置
    gateway_url = os.getenv("MCP_GATEWAY_URL", "http://8.148.226.49:5000/sse")
    api_key = os.getenv("MCP_API_KEY", "your_api_key_here")
    
    # ✅ 方式一: 使用 async with (推荐 - 自动管理生命周期)
    async with MCPClientManager(
        server_url=gateway_url,
        api_key=api_key,
        dynamic_timeout=True
    ) as client:
        
        # 获取可用工具
        print(f"可用工具: {[t.name for t in client.tools]}")
        
        # 调用云端工具 - 底层通过 JSON-RPC 复用 SSE 连接
        result = await client.call_tool(
            "calculate_tax",
            {"income": 100000, "tax_type": "income_tax", "region": "CN"}
        )
        print(f"计算结果: {result}")
        
    # ✅ 方式二: 手动管理 (需要显式调用 connect/disconnect)
    client = MCPClientManager(
        server_url=gateway_url,
        api_key=api_key
    )
    
    try:
        await client.connect()
        result = await client.call_tool("add", {"a": 99, "b": 1})
        print(f"加法结果: {result}")
    except MCPTimeoutError as e:
        print(f"工具执行超时: {e}")
    except MCPToolCallError as e:
        print(f"工具调用失败: {e}")
    finally:
        await client.disconnect()


# 应用启动时建立连接
async def startup_mcp_client():
    """在 FastAPI lifespan 中管理 MCP 客户端"""
    gateway_url = os.getenv("MCP_GATEWAY_URL", "http://8.148.226.49:5000/sse")
    api_key = os.getenv("MCP_API_KEY", "")
    
    mcp_client = MCPClientManager(
        server_url=gateway_url,
        api_key=api_key,
        dynamic_timeout=True
    )
    
    await mcp_client.connect()
    return mcp_client

```python
# 应用关闭时断开连接
async def shutdown_mcp_client(client: MCPClientManager):
    """在 FastAPI lifespan 中清理 MCP 客户端"""
    await client.disconnect()


# ============================================================================
# 附录 A: Connection Resilience - SSE 断线与自动重连
# ============================================================================

"""
⚠️ 致命问题: SSE 断线与自动重连

问题描述:
- Nginx proxy_read_timeout (默认 60s/300s) 会自动掐断空闲连接
- 如果 5 分钟内没有调用云端工具，连接被释放
- 下一分钟用户提问时，call_tool 抛出断开连接异常

解决方案: MCPClientManager 已内置自动重连机制

```python
# 1. 在 call_tool 中捕获断开异常
try:
    result = await session.call_tool(tool_name, arguments)
except (ConnectionResetError, BrokenPipeError, OSError) as e:
    # 触发重连
    await self.reconnect()
    result = await session.call_tool(tool_name, arguments)

# 2. 自动重连参数
client.call_tool("calculate_tax", {...}, auto_reconnect=True, max_retries=3)

# 3. 重连时使用指数退避
await asyncio.sleep(1 * retry_count)  # 1s, 2s, 3s...
```

详见 MCPClientManager.call_tool() 方法实现
"""


# ============================================================================
# 附录 B: 高并发连接池设计 (可选)
# ============================================================================

"""
🚧 问题: 单连接高并发瓶颈

当 100 个用户同时使用时:
- 100 个并发请求挤在同一条 SSE 信道
- JSON-RPC 支持 Multiplexing，但单点处理能力有限
- 云端 FastMCP 可能成为瓶颈

可选方案: Connection Pool (连接池)

```python
# app/mcp/connection_pool.py

import asyncio
from typing import Optional, List
from dataclasses import dataclass
from collections import deque

@dataclass
class PooledConnection:
    """连接池中的单个连接"""
    client: MCPClientManager
    in_use: bool = False
    last_used: float = 0.0

class MCPConnectionPool:
    """
    MCP 连接池管理器
    
    策略:
    1. 预热: 启动时创建 N 个连接
    2. 轮询: 调用时从池中获取可用连接
    3. 动态扩容: 连接不够时自动创建新连接
    4. 清理: 空闲超时后关闭多余连接
    
    Args:
        pool_size: 保持的连接数 (默认 5)
        max_size: 最大连接数 (默认 10)
        idle_timeout: 空闲超时秒数 (默认 300s)
    """
    
    def __init__(
        self,
        server_url: str,
        api_key: str,
        pool_size: int = 5,
        max_size: int = 10,
        idle_timeout: int = 300
    ):
        self.server_url = server_url
        self.api_key = api_key
        self.pool_size = pool_size
        self.max_size = max_size
        self.idle_timeout = idle_timeout
        
        self._pool: deque[PooledConnection] = deque()
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_size)
    
    async def initialize(self) -> None:
        """初始化连接池 - 预热 N 个连接"""
        async with self._lock:
            for _ in range(self.pool_size):
                client = MCPClientManager(self.server_url, self.api_key)
                await client.connect()
                self._pool.append(PooledConnection(client=client))
    
    async def acquire(self) -> MCPClientManager:
        """
        从池中获取可用连接
        
        策略:
        1. 有空闲连接 → 直接返回
        2. 未达上限 → 创建新连接
        3. 已达上限 → 等待释放
        """
        async with self._lock:
            # 查找空闲连接
            for conn in self._pool:
                if not conn.in_use:
                    conn.in_use = True
                    conn.last_used = asyncio.get_event_loop().time()
                    return conn.client
            
            # 未达上限，创建新连接
            if len(self._pool) < self.max_size:
                client = MCPClientManager(self.server_url, self.api_key)
                await client.connect()
                conn = PooledConnection(client=client, in_use=True)
                self._pool.append(conn)
                return client
            
            # 已达上限，等待 (这里简化处理，实际应返回 None 让调用者等待)
            raise RuntimeError("连接池已满，请稍后重试")
    
    async def release(self, client: MCPClientManager) -> None:
        """释放连接回池中"""
        async with self._lock:
            for conn in self._pool:
                if conn.client is client:
                    conn.in_use = False
                    return
    
    async def close(self) -> None:
        """关闭所有连接"""
        async with self._lock:
            for conn in self._pool:
                await conn.client.disconnect()
            self._pool.clear()


# 使用示例
async def example_with_pool():
    pool = MCPConnectionPool(
        server_url="http://8.148.226.49:5000/sse",
        api_key="your_api_key",
        pool_size=5,
        max_size=10
    )
    
    # 初始化池
    await pool.initialize()
    
    # 获取连接
    client = await pool.acquire()
    try:
        result = await client.call_tool("calculate_tax", {...})
        print(result)
    finally:
        # 释放回池
        await pool.release(client)
    
    # 关闭池
    await pool.close()
```


使用建议:
- 小规模 (< 50 并发): 单连接 + 自动重连足够
- 中等规模 (50-200 并发): 5-10 连接池
- 大规模 (> 200 并发): 需要考虑云端扩容 + 负载均衡
"""

---

## 6. LangGraph 集成 (MCP 工具适配大模型)

### 6.1 设计目标

MCP 工具需要被转换为 LangChain @tool，才能被大模型理解并自主调用。

```
┌─────────────────────────────────────────────────────────────────┐
│                    LangGraph Integration                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MCP Client Manager                                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  session.list_tools() → 获取云端工具列表                   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                           │                                    │
│                           ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  MCP → LangChain @tool 转换器                            │  │
│  │                                                          │  │
│  │  MCPToolInfo ──> @tool(name, description, args_schema)   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                           │                                    │
│                           ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  LangChain Tool Registry                                │  │
│  │                                                          │  │
│  │  @tool("calculate_tax")                                 │  │
│  │  @tool("match_legal_reference")                         │  │
│  │  @tool("generate_financial_report")                     │  │
│  │  ...                                                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│                           │                                    │
│                           ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  LLM Agent (全异步 .ainvoke)                            │  │
│  │                                                          │  │
│  │  大模型自主选择并调用 @tool                               │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 MCP 到 LangChain @tool 转换器

```python
# app/mcp/langchain_adapter.py

import asyncio
from typing import Any, Dict, List, Optional, get_type_hints, get_origin, get_args
from dataclasses import dataclass

from langchain_core.tools import BaseTool, tool
from langchain_core.callbacks import CallbackManagerForToolRun

from pydantic import BaseModel, Field, create_model

from app.mcp.client_manager import MCPClientManager, MCPToolInfo


class MCPToolAdapter:
    """
    MCP 工具适配器 - 将云端 MCP 工具转换为 LangChain @tool
    
    ⚠️ 重要设计原则: 全异步架构
    - 禁止使用 loop.run_until_complete() (会崩溃!)
    - 禁止在已运行的 event loop 中嵌套同步调用
    - 全部使用 async def + await
    """
    
    def __init__(self, mcp_client: MCPClientManager):
        self.mcp_client = mcp_client
        self._tool_cache: Dict[str, BaseTool] = {}
    
    def _infer_pydantic_type(self, schema: Dict[str, Any]) -> Any:
        """
        从 JSON Schema 深度解析 Pydantic 类型
        
        支持:
        - 基础类型: string, number, integer, boolean
        - 数组类型: items 定义
        - 对象类型: properties 定义
        - 嵌套结构: 递归解析
        - Optional: required 字段判断
        
        Args:
            schema: JSON Schema 定义
            
        Returns:
            Pydantic 类型或 Python 类型
        """
        json_type = schema.get("type")
        
        # 基础类型映射
        TYPE_MAP = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "null": type(None),
        }
        
        # 处理基础类型
        if json_type in TYPE_MAP:
            return TYPE_MAP[json_type]
        
        # 处理数组类型
        if json_type == "array":
            items_schema = schema.get("items", {})
            item_type = self._infer_pydantic_type(items_schema)
            return List[item_type]
        
        # 处理对象类型 (递归)
        if json_type == "object" or "properties" in schema:
            properties = schema.get("properties", {})
            required_fields = schema.get("required", [])
            
            field_definitions = {}
            for field_name, field_schema in properties.items():
                field_type = self._infer_pydantic_type(field_schema)
                
                # 检查是否为可选字段
                if field_name not in required_fields:
                    field_type = Optional[field_type]
                    # Pydantic V2 需要明确指定默认值
                    field_definitions[field_name] = (field_type, Field(default=None))
                else:
                    field_definitions[field_name] = (field_type, ...)
            
            # 动态创建嵌套模型
            model_name = f"DynamicObject_{len(self._nested_models)}"
            nested_model = create_model(model_name, **field_definitions)
            self._nested_models.append(nested_model)
            return nested_model
        
        # 未知类型默认返回字符串
        return str
    
    def _generate_args_schema(self, tool_info: MCPToolInfo) -> type[BaseModel]:
        """
        从云端 input_schema 生成 Pydantic V2 模型
        
        使用 Pydantic V2 的 create_model API 实现:
        - 深度嵌套解析
        - 复杂数组处理
        - Optional 字段自动识别
        
        Args:
            tool_info: MCP 工具信息
            
        Returns:
            Pydantic BaseModel 子类
        """
        self._nested_models: List[type[BaseModel]] = []
        
        properties = tool_info.input_schema.get("properties", {})
        required_fields = tool_info.input_schema.get("required", [])
        
        field_definitions = {}
        
        for param_name, param_schema in properties.items():
            description = param_schema.get("description", "")
            param_type = self._infer_pydantic_type(param_schema)
            
            # 构建字段定义
            if param_name in required_fields:
                # 必填字段
                field_definitions[param_name] = (param_type, Field(description=description))
            else:
                # 可选字段 - Pydantic V2 必须提供默认值
                field_definitions[param_name] = (
                    Optional[param_type],
                    Field(default=None, description=description)
                )
        
        # 动态创建 Pydantic 模型
        schema_name = f"{tool_info.name.title().replace('_', '')}Args"
        
        return create_model(schema_name, **field_definitions)
    
    def create_async_tool(self, tool_info: MCPToolInfo) -> BaseTool:
        """
        将单个 MCP 工具转换为 LangChain @tool (纯异步版本)
        
        ⚠️ 关键改进: 
        - 不再使用 run_until_complete
        - 直接返回协程对象，由 LangGraph 调度执行
        
        Args:
            tool_info: MCP 工具信息
            
        Returns:
            LangChain BaseTool 实例
        """
        tool_name = tool_info.name
        tool_description = tool_info.description
        
        # 获取超时配置
        timeout = 60
        if hasattr(tool_info, 'timeout_type'):
            from app.mcp.client_manager import TIMEOUT_MAP
            timeout = TIMEOUT_MAP.get(tool_info.timeout_type, 60)
        
        # 生成 Pydantic Schema
        args_schema = self._generate_args_schema(tool_info)
        
        @tool(tool_name, description=tool_description, args_schema=args_schema)
        async def wrapped_tool(
            run_manager: Optional[CallbackManagerForToolRun] = None,
            **kwargs: Any
        ) -> str:
            """
            异步工具包装器
            
            ⚠️ LangChain 会自动调度此协程，无需手动处理事件循环
            """
            try:
                # 直接 await 调用 MCP 工具
                result = await self.mcp_client.call_tool(tool_name, arguments=kwargs)
                return str(result)
                
            except asyncio.TimeoutError:
                return f"工具 {tool_name} 执行超时 ({timeout}s)"
            except Exception as e:
                return f"工具 {tool_name} 执行失败: {str(e)}"
        
        return wrapped_tool
    
    async def get_all_tools(self) -> List[BaseTool]:
        """
        获取所有云端 MCP 工具并转换为 LangChain @tool
        
        Returns:
            LangChain Tool 列表，可直接绑定到 Agent
        """
        if not self._tool_cache:
            tools = self.mcp_client.tools
            for tool_info in tools:
                langchain_tool = self.create_async_tool(tool_info)
                self._tool_cache[tool_info.name] = langchain_tool
        
        return list(self._tool_cache.values())


class LangGraphMCPIntegration:
    """
    LangGraph 与 MCP 的集成管理器
    
    使用示例:
    
    ```python
    # 初始化
    integration = LangGraphMCPIntegration(mcp_client)
    
    # 获取所有可用的云端工具
    tools = await integration.get_tools_for_agent()
    
    # 绑定到 Agent
    agent = create_react_agent(model, tools)
    ```
    """
    
    def __init__(self, mcp_client: MCPClientManager):
        self.mcp_client = mcp_client
        self.adapter = MCPToolAdapter(mcp_client)
    
    async def get_tools_for_agent(self) -> List[BaseTool]:
        """
        获取可绑定到 Agent 的工具列表
        
        Returns:
            LangChain @tool 列表
        """
        return await self.adapter.get_all_tools()
    
    async def refresh_tools(self) -> None:
        """刷新工具缓存 (当云端工具更新时)"""
        self.adapter._tool_cache.clear()
        await self.get_tools_for_agent()
```

### 6.3 使用示例

```python
# app/mcp/langgraph_example.py

import asyncio
from app.mcp.client_manager import MCPClientManager
from app.mcp.langchain_adapter import LangGraphMCPIntegration


async def main():
    """完整使用示例 - 全异步架构"""
    
    # 1. 建立 MCP 长连接
    async with MCPClientManager(
        server_url="http://8.148.226.49:5000/sse",
        api_key="your_api_key"
    ) as mcp_client:
        
        # 2. 创建 LangGraph 集成
        integration = LangGraphMCPIntegration(mcp_client)
        
        # 3. 获取所有云端工具 (已转换为 @tool)
        tools = await integration.get_tools_for_agent()
        
        print(f"已加载 {len(tools)} 个云端工具:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:50]}...")
        
        # 4. 绑定到 LangGraph Agent
        # from langgraph.prebuilt import create_react_agent
        # agent = create_react_agent(model, tools)
        
        # 5. Agent 可自主调用云端工具 (全异步!)
        # result = await agent.ainvoke({
        #     "messages": [{"role": "user", "content": "帮我计算收入100万的所得税"}]
        # })


if __name__ == "__main__":
    asyncio.run(main())
```

### 6.4 复杂嵌套 Schema 示例

```python
# 假设云端返回如下复杂 Schema:
complex_schema = {
    "type": "object",
    "properties": {
        "financial_records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "年份"},
                    "revenue": {"type": "number", "description": "收入(万元)"},
                    "expenses": {
                        "type": "object",
                        "properties": {
                            "operational": {"type": "number"},
                            "marketing": {"type": "number"}
                        }
                    }
                },
                "required": ["year", "revenue"]
            }
        },
        "analysis_type": {
            "type": "string",
            "enum": ["growth", "ratio", "forecast"]
        },
        "include_charts": {"type": "boolean", "default": False}
    },
    "required": ["financial_records", "analysis_type"]
}

# MCPToolAdapter 会自动转换为:
# class FinancialRecordsItems(BaseModel):
#     year: int
#     revenue: float
#     expenses: Optional[ExpensesObject] = None

# class FinancialAnalysisArgs(BaseModel):
#     financial_records: List[FinancialRecordsItems]
#     analysis_type: Literal["growth", "ratio", "forecast"]
#     include_charts: Optional[bool] = False  # 有 default，无需 required
```

---

## 6. 工具路由矩阵

| 工具名 | 类型 | 执行位置 | Category | 超时时间 | 依赖服务 |
|--------|------|----------|----------|----------|----------|
| `rag_retriever` | RAG | Local | - | 60s | PostgreSQL + pgvector |
| `enterprise_search` | Search | Local | - | 60s | Elasticsearch |
| `intent_classifier` | NLP | Local | - | 60s | LLM API |
| `entity_extractor` | NLP | Local | - | 60s | LLM API |
| `calculate_financial_ratio` | Calc | Cloud | finance | 10s | - |
| `analyze_cashflow` | Calc | Cloud | finance | 10s | Excel Parser |
| `forecast_financial` | LLM | Cloud | finance | 60s | LLM API |
| `compare_industry` | LLM | Cloud | finance | 60s | LLM API |
| `detect_anomaly` | Calc | Cloud | finance | 10s | - |
| `generate_financial_report` | LLM | Cloud | finance | 60s | LLM API |
| `calculate_tax` | Calc | Cloud | tax | 10s | Tax Database |
| `retrieve_tax_rules` | LLM | Cloud | tax | 60s | Tax KB |
| `check_tax_benefit` | Calc | Cloud | tax | 10s | - |
| `validate_invoice` | Calc | Cloud | tax | 10s | Tax Authority API |
| `analyze_tax_burden` | LLM | Cloud | tax | 60s | LLM API |
| `generate_filing_guide` | DocGen | Cloud | tax | 120s | Template Engine |
| `check_deduction` | Calc | Cloud | tax | 10s | - |
| `match_legal_reference` | LLM | Cloud | legal | 60s | Legal KB |
| `analyze_contract` | LLM | Cloud | legal | 60s | LLM API |
| `detect_legal_risk` | LLM | Cloud | legal | 60s | Risk Rules |
| `check_compliance` | LLM | Cloud | legal | 60s | Compliance Rules |
| `retrieve_clause` | LLM | Cloud | legal | 60s | Legal KB |
| `analyze_rights` | LLM | Cloud | legal | 60s | LLM API |
| `search_case` | LLM | Cloud | legal | 60s | Case Database |
| `render_template` | DocGen | Cloud | report | 120s | Template Engine |
| `export_pdf` | DocGen | Cloud | report | 120s | WeasyPrint |
| `export_docx` | DocGen | Cloud | report | 120s | python-docx |
| `export_xlsx` | DocGen | Cloud | report | 120s | openpyxl |
| `generate_chart` | DocGen | Cloud | report | 120s | matplotlib |
| `assemble_document` | DocGen | Cloud | report | 120s | Document Assembler |

---

## 7. 实施计划

### Phase 1: MCP Gateway 搭建

**目标**: 搭建云端 MCP 网关，实现单端口暴露

| 任务 | 工作内容 | 优先级 |
|------|----------|--------|
| Gateway 框架 | FastMCP + SSE，工具注册 | P0 |
| Finance Handler | 实现财务计算工具 | P0 |
| Tax Handler | 实现税务计算工具 | P0 |
| Health Endpoint | 健康检查接口 | P0 |

**环境要求**: Python 3.10+，网络可达 Cloud Server

### Phase 2: 安全机制

| 任务 | 工作内容 | 优先级 |
|------|----------|--------|
| Nginx 配置 | SSE 握手时 Authorization Header 校验 | P0 |
| 进门鉴权 | 仅在连接建立时验证，后续调用无需鉴权 | P0 |
| 动态超时 | asyncio.wait_for() 实现按工具类型的超时熔断 | P1 |

### Phase 3: Client 集成

| 任务 | 工作内容 | 优先级 |
|------|----------|--------|
| MCP Client Manager | 实现 SSE 长连接 + async with 生命周期管理 | P0 |
| JSON-RPC 调用 | session.call_tool() 替换 URL 路由 | P0 |
| 本地工具 | 保持现有工具不变 | P0 |

### Phase 4: LangGraph 集成

| 任务 | 工作内容 | 优先级 |
|------|----------|--------|
| @tool 包装 | 将 MCP 工具转换为 LangChain @tool | P0 |
| 工具注册 | 动态注册云端工具到 Agent | P0 |
| 自主调用 | 大模型可自主选择并调用云端工具 | P0 |

### Phase 5: 工具完善

| 任务 | 工作内容 | 优先级 |
|------|----------|--------|
| Legal Handler | 实现法律工具 | P0 |
| Report Handler | 实现报告生成工具 | P0 |

---

## 8. 超时时间汇总

| 类型 | 超时时间 | 适用工具 |
|------|----------|----------|
| **Calc** (计算类) | 10s | 财务比率计算、税务计算、发票验证等 |
| **LLM** (LLM 调用类) | 60s | 法规检索、合同分析、风险检测等 |
| **DocGen** (文档生成类) | 120s | 模板渲染、PDF/Word/Excel 导出 |
| **Default** (默认) | 60s | 未分类工具 |

---

## 9. 环境变量

```bash
# MCP Gateway 环境变量
MCP_API_KEY=mcp_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MCP_GATEWAY_HOST=0.0.0.0
MCP_GATEWAY_PORT=5000

# MCP Client 环境变量
MCP_GATEWAY_URL=https://mcp-gateway.example.com
MCP_API_KEY=mcp_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
MCP_TIMEOUT_DEFAULT=60
MCP_TIMEOUT_CALC=10
MCP_TIMEOUT_LLM=60
MCP_TIMEOUT_DOCGEN=120
```
