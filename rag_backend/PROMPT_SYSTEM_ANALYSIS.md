# 提示词加载方式分析报告

## 一、当前系统架构

### 1. BaseAgent 的提示词支持

**文件位置**：`app/agent_framework/core/base_agent.py`

BaseAgent 实现了**三层提示词加载优先级**：

```python
def _render_system_prompt(self, context: Dict[str, Any] = None, agent_name: str = None) -> str:
    """
    渲染系统提示词（优先级递减）

    1. agent_name (新结构化系统) - 优先级最高
    2. template_name (旧模板系统)
    3. system_prompt (静态提示词)
    """
```

**问题**：虽然支持新系统，但 Agent 子类在调用时**没有传递 `agent_name` 参数**，导致新系统无法被使用。

---

## 二、当前 Agent 使用情况

### 1. ReActAgent（React Agent）

```python
# react_agent.py
def __init__(self, *args, **kwargs):
    # 如果没有指定 template_name，默认使用 react_agent 模板
    if 'template_name' not in kwargs:
        kwargs['template_name'] = 'react_agent'
    super().__init__(*args, **kwargs)
```

**调用方式**：
```python
prompt = self._render_system_prompt(context)  # ❌ 没有传递 agent_name
```

**结果**：使用旧的模板系统（`templates/react_agent.txt`）

---

### 2. PlanAgent

```python
# plan_agent.py
def __init__(self, llm_adapter, tool_manager, ..., **kwargs):
    if 'template_name' not in kwargs:
        kwargs['template_name'] = 'plan_agent'
    super().__init__(llm_adapter, tool_manager, max_iterations, **kwargs)
```

**调用方式**：
```python
return self._render_system_prompt(context)  # ❌ 没有传递 agent_name
```

**结果**：使用旧的模板系统（`templates/plan_agent.txt`）

---

### 3. ReflectAgent

```python
# reflect_agent.py
DEFAULT_TEMPLATE_NAME = "reflection"

def __init__(self, ..., template_name: str = None, **kwargs):
    super().__init__(
        llm_adapter,
        tool_manager,
        template_name=template_name or self.DEFAULT_TEMPLATE_NAME,
        ...
    )
```

**调用方式**：
```python
return self._render_system_prompt(context)  # ❌ 没有传递 agent_name
```

**结果**：使用旧的模板系统（`templates/reflection.txt`）

---

### 4. OutputAgent

**特殊情况**：直接使用 PromptRegistry

```python
# output_agent.py
from app.prompts.prompt_registry import get_prompt_registry

# 在某个方法中
prompt = registry.load_system_prompt("output_agent")
```

**结果**：部分使用新系统，但代码混乱，既有 PromptRegistry 加载，也有旧的提示词导入。

---

### 5. ReportAgent

**完全独立**：没有继承 BaseAgent，自己管理提示词。

---

## 三、新结构化提示词系统

### 目录结构

```
app/prompts/agents/
├── report_agent/
│   ├── agent.yaml          # Agent 配置文件
│   ├── system.md          # 主系统提示词
│   ├── financial_report.md # 子提示词
│   ├── sales_report.md
│   ├── inventory_report.md
│   └── operation_report.md
├── output_agent/
│   ├── agent.yaml
│   ├── system.md
│   ├── synthesis.md
│   ├── quick_review.md
│   ├── deep_review.md
│   └── regeneration.md
├── plan_agent/
│   ├── agent.yaml
│   └── system.md
├── reflection_agent/
│   ├── agent.yaml
│   └── system.md
└── ...
```

### PromptRegistry 的功能

```python
class AgentPromptRegistry:
    def load_system_prompt(self, agent_name: str) -> Optional[str]:
        """
        加载智能体系统提示词

        优先级：
        1. agents/{agent_name}/system.md (新结构)
        2. agents/{agent_name}/agent.yaml 指定的 fallback_file (向后兼容)
        3. templates/{agent_name}.txt (旧结构)
        """
```

**问题**：虽然支持 `agent.yaml` 中的 `sub_prompts`，但没有提供加载子提示词的接口。

---

## 四、存在的问题

### 1. Agent 未充分利用新系统

| Agent | 初始化 | 调用方式 | 实际使用 |
|-------|--------|----------|----------|
| ReActAgent | template_name='react_agent' | _render_system_prompt(context) | ❌ 旧模板 |
| PlanAgent | template_name='plan_agent' | _render_system_prompt(context) | ❌ 旧模板 |
| ReflectAgent | template_name='reflection' | _render_system_prompt(context) | ❌ 旧模板 |
| OutputAgent | - | registry.load_system_prompt() | ⚠️ 部分使用 |
| ReportAgent | - | 独立管理 | ❌ 未使用 |

**根本原因**：Agent 子类在调用 `_render_system_prompt()` 时**没有传递 `agent_name` 参数**。

---

### 2. 子提示词加载功能缺失

`PromptRegistry` 设计了 `sub_prompts` 配置：

```yaml
# agent.yaml
prompt:
  system_file: "system.md"
  sub_prompts:
    - name: "synthesis"
      file: "synthesis.md"
    - name: "quick_review"
      file: "quick_review.md"
```

但没有提供加载这些子提示词的方法。OutputAgent 只能通过 `OutputAgentPrompts._load_prompt_file()` 手动加载。

---

### 3. 不一致的迁移进度

- **OutputAgent**：部分迁移，有两套代码
- **其他 Agent**：未迁移，继续使用旧模板

---

## 五、建议的改进方案

### 方案一：Agent 统一迁移（推荐）

**目标**：让所有 Agent 使用新的结构化提示词系统

**改进点**：

1. **BaseAgent 添加 `agent_name` 支持**：
   ```python
   def __init__(
       self,
       llm_adapter,
       tool_manager,
       agent_name: str = None,  # 新增参数
       template_name: str = None,
       system_prompt: str = "",
       ...
   ):
       self.agent_name = agent_name
       self.template_name = template_name
       self.system_prompt = system_prompt
   ```

2. **子类 Agent 更新初始化**：
   ```python
   # ReActAgent
   def __init__(self, *args, agent_name: str = "react_agent", **kwargs):
       super().__init__(*args, agent_name=agent_name, **kwargs)

   # PlanAgent
   def __init__(self, *args, agent_name: str = "plan_agent", **kwargs):
       super().__init__(*args, agent_name=agent_name, **kwargs)
   ```

3. **子类 Agent 调用时传递 agent_name**：
   ```python
   # ReActAgent
   prompt = self._render_system_prompt(context, agent_name=self.agent_name)

   # PlanAgent
   return self._render_system_prompt(context, agent_name=self.agent_name)
   ```

---

### 方案二：补充子提示词加载功能

**目标**：让 Agent 能够加载 `agent.yaml` 中定义的子提示词

**改进点**：

1. **PromptRegistry 添加子提示词加载方法**：
   ```python
   def load_sub_prompt(self, agent_name: str, sub_prompt_name: str) -> Optional[str]:
       """加载子提示词"""
       config = self.get_agent(agent_name)
       if not config:
           return None

       sub_prompts = config.get('prompt', {}).get('sub_prompts', [])
       for sub_prompt in sub_prompts:
           if sub_prompt['name'] == sub_prompt_name:
               file_path = self.agents_dir / agent_name / sub_prompt['file']
               if file_path.exists():
                   return file_path.read_text(encoding='utf-8')

       return None
   ```

2. **OutputAgent 使用统一接口**：
   ```python
   # 替换手动加载
   synthesis_prompt = registry.load_sub_prompt("output_agent", "synthesis")
   review_prompt = registry.load_sub_prompt("output_agent", "quick_review")
   ```

---

### 方案三：添加迁移辅助功能

**目标**：帮助 Agent 从旧系统平滑迁移到新系统

**改进点**：

1. **自动生成 agent.yaml**：
   ```python
   def migrate_from_template(agent_name: str, template_name: str):
       """
       从旧模板迁移到新结构

       1. 读取 templates/{template_name}.txt
       2. 创建 agents/{agent_name}/ 目录
       3. 生成 system.md 和 agent.yaml
       """
   ```

2. **Agent 初始化时自动回退**：
   ```python
   # BaseAgent.__init__()
   if agent_name and not self.prompt_engine.template_exists(agent_name):
       # 如果新系统不存在，尝试旧模板
       if template_name:
           self.template_name = template_name
           self.use_template = True
           print(f"[WARNING] {agent_name} 不存在，使用回退模板 {template_name}")
   ```

---

## 六、实施步骤

### Phase 1：基础设施完善（1天）

1. [ ] PromptRegistry 添加 `load_sub_prompt()` 方法
2. [ ] BaseAgent 添加 `agent_name` 参数支持
3. [ ] 添加迁移辅助函数

### Phase 2：Agent 迁移（2天）

1. [ ] ReActAgent 迁移到新系统
2. [ ] PlanAgent 迁移到新系统
3. [ ] ReflectAgent 迁移到新系统
4. [ ] OutputAgent 清理旧代码，使用统一接口
5. [ ] ReportAgent 集成 BaseAgent

### Phase 3：测试和文档（1天）

1. [ ] 测试所有 Agent 的提示词加载
2. [ ] 更新架构文档
3. [ ] 添加使用示例

---

## 七、关键文件清单

| 文件 | 作用 | 状态 | 备注 |
|------|------|------|------|
| `base_agent.py` | Agent 基类，提示词渲染 | ⚠️ 部分支持 | 需要添加 agent_name |
| `prompt_registry.py` | 结构化提示词注册表 | ✅ 已实现 | 需要添加子提示词加载 |
| `prompt_service.py` | 模板引擎 | ✅ 已实现 | - |
| `react_agent.py` | ReAct Agent | ❌ 未迁移 | 需要迁移 |
| `plan_agent.py` | Plan Agent | ❌ 未迁移 | 需要迁移 |
| `reflect_agent.py` | Reflect Agent | ❌ 未迁移 | 需要迁移 |
| `output_agent.py` | Output Agent | ⚠️ 部分迁移 | 需要清理 |
| `report_agent.py` | Report Agent | ❌ 独立实现 | 需要集成 |

---

## 八、总结

### 当前状态

✅ **新结构化提示词系统基础设施已就绪**：
- 目录结构设计完成
- PromptRegistry 核心功能已实现
- BaseAgent 预留了支持接口

❌ **Agent 未充分利用新系统**：
- 大部分 Agent 仍在使用旧模板系统
- 没有传递 `agent_name` 参数
- 子提示词加载功能缺失

### 建议

1. **立即行动**：让 Agent 传递 `agent_name` 参数，充分利用已有基础设施
2. **短期**：补充子提示词加载功能
3. **中期**：统一所有 Agent 到新系统，清理旧代码

这样可以实现用户提到的目标：
- ✅ 不需要统一的系统提示词（每个 Agent 独立）
- ✅ 不需要引擎（PromptRegistry + PromptEngine 组合）
- ✅ 静态提示词分散管理（通过 `agent.yaml` 配置）
