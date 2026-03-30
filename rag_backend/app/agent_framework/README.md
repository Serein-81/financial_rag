# 自定义 Agent 框架

一个简洁、易懂的 Agent 实现，专为学习和理解 Agent 原理而设计。

## 🎯 设计目标

- **简单易懂**: 核心代码不超过 500 行，每个模块职责清晰
- **学习价值**: 深入理解 ReAct、Plan-and-Solve、Reflect 等推理模式
- **高度可控**: 每一行代码都清楚，易于调试和修改
- **兼容性好**: 支持 LangChain 工具，可以随时切换

## 📁 目录结构

```
agent_framework/
├── __init__.py                 # 框架入口
├── core/                       # 核心模块
│   ├── __init__.py
│   ├── base_agent.py          # Agent 抽象基类
│   ├── react_agent.py         # ReAct 模式实现
│   ├── plan_solve_agent.py    # Plan-and-Solve 模式（待实现）
│   └── reflect_agent.py       # Reflect 模式（待实现）
├── tools/                      # 工具管理
│   ├── __init__.py
│   ├── tool_manager.py        # 工具管理器
│   └── langchain_compat.py    # LangChain 兼容层
├── llm/                        # LLM 适配器
│   ├── __init__.py
│   ├── base_adapter.py        # 抽象基类
│   ├── zhipu_adapter.py       # 智谱 AI 适配器
│   └── openai_adapter.py      # OpenAI 适配器（待实现）
└── README.md                   # 本文档
```

## 🚀 快速开始

### 1. 基本使用

```python
from app.agent_framework import ReActAgent, ToolManager, ZhipuAdapter

# 初始化组件
llm_adapter = ZhipuAdapter(api_key="your_api_key")
tool_manager = ToolManager()
agent = ReActAgent(llm_adapter, tool_manager)

# 执行对话
answer = await agent.run("你好，今天天气怎么样？")
print(answer)
```

### 2. 注册工具

```python
# 注册普通函数
async def get_weather(city: str) -> str:
    return f"{city}今天晴天，25°C"

tool_manager.register_function(
    name="get_weather",
    func=get_weather,
    description="查询城市天气"
)

# 注册 LangChain 工具
from app.tools import get_all_tools
from app.agent_framework.tools import LangChainCompatLayer

langchain_tools = get_all_tools()
compat_layer = LangChainCompatLayer(tool_manager)
compat_layer.register_langchain_tools(langchain_tools)
```

### 3. 流式输出

```python
async for chunk in agent.stream_run("请介绍一下人工智能"):
    print(chunk, end="", flush=True)
```

## 🧠 Agent 模式

### ReAct (Reasoning and Acting)

**核心思想**: 思考-行动-观察的循环

**执行流程**:
```
1. Thought: 分析问题，决定下一步
2. Action: 调用工具或给出答案
3. Observation: 观察工具结果
4. 重复 1-3 直到得出最终答案
```

**适用场景**: 
- 需要多步推理的问题
- 需要调用外部工具的任务
- 大部分日常对话场景

### Plan-and-Solve (待实现)

**核心思想**: 先制定计划，再按计划执行

**执行流程**:
```
1. 分析问题，制定完整计划
2. 按计划顺序执行每个步骤
3. 收集所有结果
4. 整合信息，生成最终答案
```

**适用场景**:
- 复杂的多步骤任务
- 需要并行执行的操作
- 有明确步骤的流程

### Reflect (待实现)

**核心思想**: 执行-反思-改进的循环

**执行流程**:
```
1. 尝试回答或执行任务
2. 评估结果质量
3. 如果不满意，分析问题
4. 调整策略，重新执行
5. 重复直到满意或达到限制
```

**适用场景**:
- 需要高质量输出的任务
- 容易出错的复杂操作
- 需要自我改进的场景

## 🛠️ 工具系统

### 工具管理器 (ToolManager)

负责工具的注册、调用和管理：

```python
# 注册函数工具
tool_manager.register_function(
    name="calculator",
    func=calculate,
    description="执行数学计算"
)

# 注册 LangChain 工具
tool_manager.register_langchain_tool(langchain_tool)

# 调用工具
result = await tool_manager.call_tool("calculator", expression="2+3")

# 获取工具描述
description = tool_manager.get_tools_description()
```

### LangChain 兼容层

自动转换 LangChain 工具：

```python
from app.agent_framework.tools import LangChainCompatLayer

compat_layer = LangChainCompatLayer(tool_manager)
compat_layer.register_langchain_tools(langchain_tools)
```

## 🤖 LLM 适配器

### 智谱 AI 适配器

```python
from app.agent_framework.llm import ZhipuAdapter

adapter = ZhipuAdapter(
    api_key="your_api_key",
    model_name="glm-4-flash"
)

# 非流式生成
response = await adapter.generate("你好")

# 流式生成
async for chunk in adapter.stream_generate("你好"):
    print(chunk, end="")
```

### 自定义适配器

继承 `BaseLLMAdapter` 实现自己的适配器：

```python
from app.agent_framework.llm import BaseLLMAdapter

class CustomAdapter(BaseLLMAdapter):
    async def generate(self, prompt, **kwargs):
        # 实现你的生成逻辑
        pass
    
    async def stream_generate(self, prompt, **kwargs):
        # 实现你的流式生成逻辑
        pass
```

## 🔧 配置选项

### Agent 配置

```python
agent = ReActAgent(
    llm_adapter=llm_adapter,
    tool_manager=tool_manager,
    system_prompt="你是一个智能助手",
    max_iterations=10,      # 最大迭代次数
    timeout=300.0          # 超时时间（秒）
)
```

### 环境变量控制

```bash
# 选择使用的框架
USE_CUSTOM_AGENT=true     # 使用自定义框架
USE_CUSTOM_AGENT=false    # 使用 LangChain

# API 配置
ZHIPU_API_KEY=your_key
```

## 📊 监控和调试

### 执行日志

Agent 会自动记录执行过程：

```python
# 获取执行摘要
summary = agent.get_execution_summary()
print(f"总迭代次数: {summary['total_iterations']}")
print(f"工具调用次数: {summary['tool_calls']}")
print(f"执行时间: {summary['total_time']} 秒")

# 查看详细日志
for log_entry in agent.execution_log:
    print(f"[{log_entry['iteration']}] {log_entry['action']}")
```

### 工具统计

```python
# 工具管理器摘要
summary = tool_manager.get_summary()
print(f"总工具数: {summary['total_tools']}")
print(f"工具类型: {summary['tool_types']}")
```

## 🧪 测试

运行测试脚本：

```bash
cd rag_backend
python test_custom_agent.py
```

测试内容：
- 基本功能初始化
- 简单问答（不需要工具）
- 工具调用（天气查询等）
- 流式输出
- 工具管理器功能

## 🔄 与 LangChain 对比

| 特性 | 自定义框架 | LangChain |
|------|-----------|-----------|
| 代码复杂度 | ⭐⭐ 简单 | ⭐⭐⭐⭐ 复杂 |
| 学习价值 | ⭐⭐⭐⭐⭐ 很高 | ⭐⭐ 一般 |
| 可控性 | ⭐⭐⭐⭐⭐ 完全可控 | ⭐⭐ 黑盒较多 |
| 功能完整性 | ⭐⭐⭐ 核心功能 | ⭐⭐⭐⭐⭐ 功能丰富 |
| 性能 | ⭐⭐⭐⭐ 轻量 | ⭐⭐⭐ 较重 |
| 扩展性 | ⭐⭐⭐⭐ 易扩展 | ⭐⭐⭐⭐⭐ 生态丰富 |

## 🛣️ 发展路线

### 已完成 ✅
- [x] BaseAgent 抽象基类
- [x] ReActAgent 实现
- [x] ToolManager 工具管理器
- [x] ZhipuAdapter LLM 适配器
- [x] LangChain 兼容层
- [x] 流式输出支持

### 进行中 🚧
- [ ] Plan-and-Solve Agent
- [ ] Reflect Agent
- [ ] OpenAI 适配器

### 计划中 📋
- [ ] 更多 LLM 适配器
- [ ] 工具调用并发执行
- [ ] 更丰富的监控功能
- [ ] 性能优化

## 🤝 贡献指南

欢迎贡献代码！请遵循以下原则：

1. **保持简洁**: 优先考虑代码的可读性和简洁性
2. **充分测试**: 新功能需要包含测试用例
3. **文档完善**: 重要功能需要更新文档
4. **向后兼容**: 避免破坏现有 API

## 📄 许可证

MIT License - 详见 LICENSE 文件

## 🙋‍♂️ 常见问题

### Q: 为什么要自己实现 Agent 框架？
A: 为了深入理解 Agent 的工作原理，提高代码的可控性，减少对外部框架的依赖。

### Q: 性能如何？
A: 由于去除了不必要的抽象层，性能通常比 LangChain 更好，特别是在简单场景下。

### Q: 如何添加新的 Agent 模式？
A: 继承 `BaseAgent` 类，实现 `run` 和 `stream_run` 方法即可。

### Q: 可以与 LangChain 混用吗？
A: 可以，通过兼容层可以使用 LangChain 的工具，也可以随时切换回 LangChain。

### Q: 如何调试 Agent 执行过程？
A: 查看 `agent.execution_log` 获取详细的执行日志，或使用 `get_execution_summary()` 获取摘要。