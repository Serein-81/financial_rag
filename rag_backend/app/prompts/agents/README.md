# Agent Prompts

本目录保存结构化 Agent 提示词。后端通过 `app/prompts/loader.py` 中的 `AgentPromptLoader` 读取 `agent.yaml` 和对应的 `system.md`，供 ReAct、规划、税务、法务、财务、报告、政策通知等 Agent 使用。

## 当前目录结构

```text
prompts/agents/
  finance/
    agent.yaml
    system.md
  intent_router/
    agent.yaml
    system.md
  legal/
    agent.yaml
    system.md
  orchestrator/
    agent.yaml
    system.md
  output/
    agent.yaml
    system.md
    prompts.md
  plan/
    agent.yaml
    system.md
  policy_notification/
    agent.yaml
    system.md
  react/
    agent.yaml
    system.md
  report/
    agent.yaml
    system.md
  tax/
    agent.yaml
    system.md
    invoice_recognition.md
    invoice_recognition_enhanced.md
```

共享提示词片段不在本目录下，而在：

```text
prompts/shared/
  common_rules.yaml
  output_style.yaml
  rag_context.yaml
  tool_fallback.yaml
```

工具技能提示词位于：

```text
prompts/skills/
  get_location_info.txt
  get_weather.txt
  list_knowledge_documents.txt
  search_enterprise_knowledge.txt
  search_web.txt
  send_email.txt
```

## 加载机制

核心加载器：`app/prompts/loader.py`

主要接口：

- `AgentPromptLoader.load_agent_config(agent_name)`：读取 `agents/{agent_name}/agent.yaml`。
- `AgentPromptLoader.load_system_prompt(agent_name)`：读取该 Agent 的 system prompt。
- `AgentPromptLoader.render_prompt(agent_name, context)`：用 `str.format` 渲染变量。
- `AgentPromptLoader.load_shared_component(name)`：读取 `prompts/shared` 中的 yaml/md 片段。
- `get_agent_prompt_loader()`：获取全局单例。
- `load_agent_prompt(agent_name)`：快捷读取 system prompt。
- `list_available_agents()` / `get_all_agents()`：列出可用 Agent。

`AgentPromptRegistry` 目前是 `AgentPromptLoader` 的兼容别名。

## agent.yaml 约定

当前 loader 会从配置中读取：

```yaml
agent:
  name: react
  display_name: ReAct Agent
  prompts:
    system: system.md
```

如果 `agent.prompts.system` 不存在，默认读取同目录下的 `system.md`。

不同 Agent 的 YAML 还可以包含模型、能力、工具、元数据等业务配置；这些字段由具体 Agent 或服务自行解释，loader 只负责读取和缓存。

## 使用示例

```python
from app.prompts.loader import get_agent_prompt_loader, load_agent_prompt

loader = get_agent_prompt_loader()

agents = loader.get_available_agents()
tax_prompt = load_agent_prompt("tax")

rendered = loader.render_prompt(
    "react",
    {
        "user_input": "查询企业所得税优惠政策",
        "tools_description": "...",
        "max_iterations": 5,
    },
)
```

## 维护规范

- 每个 Agent 一个独立目录，至少包含 `agent.yaml` 和 `system.md`。
- 新增 Agent 后，确认 `AgentPromptLoader.get_available_agents()` 能看到它。
- `system.md` 中如果使用 `{variable}`，必须保证调用 `render_prompt` 时提供该变量。
- 共享规则放到 `prompts/shared/`，不要在多个 Agent 文档中复制粘贴。
- 工具调用说明或可复用技能放到 `prompts/skills/`。
- 税务、法务、财务等高风险提示词要明确输出边界、证据要求、免责声明和人工复核触发条件。
- 避免在 prompt 中写死密钥、租户 ID、真实用户数据或生产地址。

## 缓存与热更新

`AgentPromptLoader` 会缓存配置和 prompt 文本。修改提示词后，如果进程未重启，可以调用：

```python
loader.reload_agent("tax")
loader.clear_cache()
```

## 测试建议

```bash
cd rag_backend
pytest tests/unit/test_prompt_engine.py
pytest tests/agent_system/test_new_agent_templates.py
pytest tests/agent_system/test_agent_template_integration.py
```

如果测试中提示找不到 Agent，先检查目录名是否与调用的 `agent_name` 一致，以及 `agent.yaml` 是否存在。
