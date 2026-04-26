# 提示词结构化重构

## 目录结构

```
prompts/
├── agents/                          # 结构化的智能体提示词目录
│   ├── react_agent/                 # ReAct 推理智能体
│   │   ├── agent.yaml              # 配置文件
│   │   ├── system.md               # 系统提示词
│   │   ├── skills/                 # 技能片段（可选）
│   │   └── examples/               # 示例文件
│   │       ├── simple_greeting.yaml
│   │       └── rag_query.yaml
│   │
│   ├── plan_agent/                 # 计划执行智能体
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   ├── skills/
│   │   └── examples/
│   │
│   ├── reflection_agent/           # 反思智能体
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   ├── skills/
│   │   └── examples/
│   │
│   ├── smart_router/               # 智能路由智能体
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   ├── skills/
│   │   └── examples/
│   │       └── routing_decisions.yaml
│   │
│   ├── triage_agent/               # 分类智能体
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── skills/
│   │
│   ├── output_agent/               # 输出格式化智能体（已弃用，向后兼容）
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── skills/
│   │
│   ├── report_agent/               # 报告生成智能体
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── skills/
│   │
│   └── shared/                     # 共享提示词片段
│       ├── common_rules.md         # 通用对话规则
│       ├── rag_context.md          # RAG 上下文格式
│       └── output_style.md         # 输出样式规范
│
├── templates/                       # 旧版提示词（保留，向后兼容）
│   ├── react_agent.txt
│   ├── plan_agent.txt
│   ├── reflection.txt
│   └── output.txt
│
├── system/                          # 旧版系统提示词（已废弃）
│   ├── smart_router_agent.md
│   ├── triage_agent.md
│   ├── finance_agent.md
│   └── legal_agent.md
│
└── __init__.py                      # 提示词加载接口
```

## agent.yaml 配置说明

每个智能体的 `agent.yaml` 文件包含以下配置：

```yaml
agent:
  name: "agent_name"                # 唯一标识
  display_name: "显示名称"           # 友好名称
  version: "1.0.0"                  # 版本号
  mode: "react"                     # 运行模式
  description: "描述"                # 详细描述

prompt:
  system_file: "system.md"          # 主系统提示词
  fallback_file: "../../templates/react_agent.txt"  # 兼容模式回退文件

compatibility_mode:
  enabled: true                     # 是否启用向后兼容
  fallback_file: "../../templates/react_agent.txt"  # 回退文件路径

variables:
  - name: "variable_name"
    type: "string"
    required: true
    default: "default_value"
    description: "变量描述"

metadata:
  created_at: "2024-01-01"
  author: "team"
  tags: ["tag1", "tag2"]
```

## 新旧结构对比

| 特性 | 旧结构 | 新结构 |
|------|--------|--------|
| 组织方式 | 扁平化 | 按智能体分类 |
| 配置文件 | 无 | YAML 配置 |
| 示例 | 无 | 内置示例 |
| 版本控制 | 无 | 支持版本号 |
| 类型安全 | 无 | 变量类型定义 |
| 向后兼容 | 原生支持 | 通过 fallback |
| 扩展性 | 困难 | 模块化设计 |

## 使用方式

### 加载智能体提示词

```python
from app.prompts import AgentPromptRegistry

# 获取智能体提示词
registry = AgentPromptRegistry()
prompt_config = registry.get_agent("react_agent")

# 渲染提示词
rendered = registry.render_prompt(
    "react_agent",
    user_input="你好",
    tools_description="...",
    max_iterations=5
)
```

### 获取提示词路径

```python
from app.prompts import AgentPromptRegistry

registry = AgentPromptRegistry()
system_prompt_path = registry.get_prompt_path("react_agent")
```

## 迁移指南

### 从旧结构迁移

1. **保留旧文件**：所有 `templates/` 下的文件保持不变
2. **创建新结构**：在 `agents/` 下创建新的组织结构
3. **配置 fallback**：在新结构的 `agent.yaml` 中配置 `fallback_file`
4. **逐步迁移**：逐个智能体迁移提示词内容

### 回退机制

当新结构出现问题时，系统会自动回退到 `fallback_file` 指定的旧文件。

## 最佳实践

1. **保持简洁**：每个 `system.md` 专注于一个职责
2. **版本控制**：更新时递增版本号
3. **添加示例**：为复杂智能体添加示例文件
4. **文档注释**：为变量和配置添加注释
5. **测试覆盖**：为提示词变化编写测试用例
