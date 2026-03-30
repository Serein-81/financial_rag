# 提示词管理系统

> **🚀 版本升级通知** 
> 
> 本系统已从简单版 `prompt_loader.py` 升级到高级版 `prompt_service.py`！
> 
> **升级内容**：
> - ✨ 支持变量替换 `{variable_name}`
> - ✨ 支持条件渲染 `{% if condition %}`
> - ✨ 支持循环渲染 `{% for item in items %}`
> - ✨ 支持 Skills 自动加载
> - ✨ 智能缓存优化
> - 🎯 完全向后兼容，API 无变化

## 📁 目录结构

```
app/prompts/
├── PROMPTS_README.md          # 【核心大纲】记录有哪些模板、变量怎么传、A/B测试
├── agent_system.txt          # 【主力提示词】Agent 核心系统提示词
├── system/                    # 【独立灵魂】真正的提示词文件存放在这里
│   ├── reflection_agent.md    # 反思协调官提示词
│   ├── finance_agent.md       # 财务审计官提示词（等待编写）
│   ├── tax_agent.md          # 税务合规官提示词（等待编写）
│   └── legal_agent.md        # 法务审查官提示词（等待编写）
├── skills/                    # 技能型提示词
│   ├── search_enterprise_knowledge.txt  # 企业知识库检索
│   ├── get_weather.txt       # 天气查询
│   ├── get_location_info.txt # 地理位置查询
│   └── search_web.txt        # 网络搜索
└── templates/                 # 模板型提示词（高级功能）
```

## 🎯 设计理念

### 1. 独立灵魂原则
每个 Agent 的提示词都是独立的 Markdown 文件，包含：
- 角色定位
- 核心职责
- 工作流程
- 输出格式
- 注意事项

### 2. 变量传递机制
提示词中使用占位符，由代码动态替换：
- `{query}` - 用户查询
- `{context}` - 检索到的上下文
- `{history}` - 对话历史
- `{specialist_results}` - 专家分析结果

### 3. A/B 测试支持
- 每个提示词可以有多个版本
- 通过 `prompt_optimization` 表记录测试结果
- 支持自动选择最优版本

## 📝 提示词编写规范

### 基本结构
```markdown
# Agent 名称

## 角色定位
你是一个...

## 核心职责
1. ...
2. ...

## 工作流程
### 步骤1：...
### 步骤2：...

## 输出格式
```json
{
  "field": "value"
}
```

## 注意事项
- ...
```

### 变量使用
在提示词中使用 `{variable_name}` 格式的占位符，代码会自动替换。

### 版本管理
- 文件名：`agent_name.md` 或 `agent_name_v2.md`
- 在数据库中记录版本号和性能指标

## 🔧 使用方式

### 方式一：通用提示词加载（兼容旧版，推荐）

```python
from app.services.prompt_service import load_agent_system_prompt

# 加载 Agent 核心系统提示词
prompt = load_agent_system_prompt()
print(prompt)
```

### 方式二：高级模板渲染（支持变量替换）

```python
from app.services.prompt_service import render_prompt

# 渲染模板，支持变量替换
filled_prompt = render_prompt(
    "qa_prompt",
    context="检索到的上下文...",
    question="用户问题"
)
print(filled_prompt)
```

### 方式三：完整控制（使用 PromptEngine）

```python
from app.services.prompt_service import PromptEngine, prompt_engine

# 方式A：使用全局单例
result = prompt_engine.render(
    "qa_prompt",
    variables={
        "context": "上下文",
        "question": "问题"
    },
    load_skills=True  # 自动加载工具对应的 Skills
)

# 方式B：创建自定义实例
engine = PromptEngine(
    templates_dir="/path/to/templates",
    skills_dir="/path/to/skills",
    prompts_root="/path/to/prompts"
)
result = engine.render("template_name", variables={...})
```

### 方式四：A/B 测试（待实现）

```python
# 自动选择最优版本
prompt = await prompt_service.get_best_prompt("reflection_agent")

# 记录测试结果
await prompt_service.record_result(
    prompt_id=prompt.id,
    success=True,
    response_time=1.5
)
```

## 📊 性能监控

系统会自动记录每个提示词的：
- 使用次数
- 成功率
- 平均响应时间
- 用户满意度

通过 `/api/v1/prompt-optimization/stats` 查看统计数据。

## 🚀 待完成任务

- [ ] 编写 finance_agent.md 提示词
- [ ] 编写 tax_agent.md 提示词
- [ ] 编写 legal_agent.md 提示词
- [ ] 完善变量传递文档
- [ ] 添加更多示例

## 📚 参考资料

- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [OpenAI Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)
