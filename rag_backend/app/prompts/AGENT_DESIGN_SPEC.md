# Agent提示词架构设计规范

## 1. 设计原则

### 1.1 核心原则
- **一个Agent只有一份定义**：避免重复和冗余
- **统一结构**：所有Agent遵循相同的目录结构
- **可扩展性**：支持新增Agent类型
- **可维护性**：清晰的命名和分类
- **动态加载**：支持运行时热更新

### 1.2 Agent分类体系

#### A. 推理引擎（Reasoning Engines）
基础推理模式，作为其他Agent的基类：
- `react` - ReAct推理（Reasoning + Acting）
- `plan` - Plan-Execute（计划执行）
- `reflect` - Reflect-Refine（反思改进）

#### B. 专业领域专家（Specialist Agents）
垂直领域的AI专家：
- `triage` - 门卫/分流专家（文档分类、安全过滤）
- `tax` - 税务专家
- `finance` - 财务专家
- `legal` - 法务专家
- `policy` - 政策通知专家

#### C. 协调层（Coordination Layer）
负责任务调度和协调：
- `intent_router` - 意图路由（用户输入分类）
- 质量审查：使用 `llm_functions.review_quality()` 函数

#### D. 输出层（Output Layer）
负责结果处理和呈现：
- `output` - 输出合成与审查
- `report` - 报告生成（合并业务报表）

## 2. 目录结构

```
prompts/
│
├── agents/                          # Agent定义目录
│   │
│   ├── react/                       # ReAct推理引擎
│   │   ├── agent.yaml               # Agent配置
│   │   ├── system.md                # 系统提示词
│   │   ├── FewShot/                 # 少样本示例
│   │   │   ├── simple.yaml
│   │   │   └── complex.yaml
│   │   └── tools/                   # 工具提示词片段
│   │       └── common.yaml
│   │
│   ├── plan/                        # 计划执行引擎
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   ├── phases/                  # 阶段提示词
│   │   │   ├── planning.md
│   │   │   ├── execution.md
│   │   │   └── monitoring.md
│   │   └── FewShot/
│   │
│   ├── reflect/                     # 反思改进引擎
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   ├── phases/
│   │   │   ├── action.md
│   │   │   ├── reflection.md
│   │   │   └── refinement.md
│   │   └── FewShot/
│   │
│   ├── triage/                      # 门卫专家
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── validation/              # 验证规则
│   │       └── security.md
│   │
│   ├── tax/                         # 税务专家
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── domains/                 # 子领域
│   │       ├── vat.md
│   │       ├── income.md
│   │       └── personal.md
│   │
│   ├── finance/                     # 财务专家
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── domains/
│   │       ├── investment.md
│   │       ├── loan.md
│   │       └── budget.md
│   │
│   ├── legal/                       # 法务专家
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── domains/
│   │       ├── contract.md
│   │       ├── ip.md
│   │       └── compliance.md
│   │
│   ├── policy/                      # 政策通知专家
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── matching/                # 匹配规则
│   │       └── enterprise.md
│   │
│   ├── intent_router/               # 意图路由
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   └── patterns/                # 模式匹配
│   │       ├── greetings.md
│   │       └── queries.md
│   │
│   ├── output/                      # 输出合成专家
│   │   ├── agent.yaml
│   │   ├── system.md
│   │   ├── strategies/              # 合成策略
│   │   │   ├── merge.md
│   │   │   ├── narrative.md
│   │   │   └── hierarchical.md
│   │   └── review/                  # 审查模板
│   │       ├── quick.md
│   │       └── deep.md
│   │
│   └── report/                      # 报告生成专家
│       ├── agent.yaml
│       ├── system.md
│       └── templates/               # 报告模板
│           ├── sales.md
│           ├── financial.md
│           └── executive.md
│
├── shared/                          # 共享组件
│   ├── common_rules.yaml            # 通用规则
│   ├── output_style.yaml            # 输出格式规范
│   ├── communication.yaml          # 通信协议
│   └── rag_context.yaml             # RAG上下文
│
├── skills/                          # 工具Skills定义
│   ├── search_knowledge.yaml
│   ├── query_database.yaml
│   ├── calculate.yaml
│   └── ...
│
├── templates/                       # 基础模板
│   ├── base_agent.yaml              # Agent基类模板
│   └── dynamic_loader.py            # 动态加载器
│
├── __init__.py                      # 包初始化
├── registry.py                      # Agent注册表
└── loader.py                        # 统一加载器
```

## 3. Agent配置文件规范

### 3.1 agent.yaml 结构
```yaml
agent:
  name: "tax"                        # Agent唯一标识
  display_name: "税务专家"            # 显示名称
  version: "1.0.0"                   # 版本号
  type: "specialist"                 # Agent类型
  description: "处理企业税务相关问题"
  
  # 推理引擎配置（可选）
  reasoning:
    engine: "react"                  # 使用的推理引擎
    max_iterations: 10
    timeout: 60
    
  # 提示词文件
  prompts:
    system: "system.md"              # 主系统提示词
    fewshot_dir: "FewShot/"          # 少样本目录
    
  # 工具配置
  tools:
    enabled: true
    required: []                     # 必须工具
    optional: []                     # 可选工具
    
  # 领域配置（专业Agent）
  domains:                           # 子领域定义
    - vat
    - income_tax
    - personal_income_tax
    
  # 输出配置
  output:
    format: "structured"            # 输出格式
    confidence_required: true        # 需要置信度
    
  # 元数据
  metadata:
    author: "AI Team"
    created: "2024-01-01"
    tags: ["tax", "finance", "expert"]
```

### 3.2 system.md 结构
```markdown
# 税务专家系统提示词

## 角色定义
你是一名资深税务专家，拥有丰富的税务知识和实践经验...

## 核心职责
1. 税务政策咨询与解读
2. 税务计算与申报指导
3. 发票管理与合规检查
...

## 专业知识领域
{domain_knowledge}

## 工作流程
1. 理解用户问题
2. 识别税种类型
3. 分析相关法规
4. 提供专业建议
...

## 输出规范
{output_format}

## 约束条件
{constraints}
```

## 4. 动态加载机制

### 4.1 加载优先级
1. 环境变量指定的路径（最高优先级）
2. `prompts/agents/{agent_name}/system.md`
3. `prompts/agents/{agent_name}/agent.yaml` 中的配置
4. 默认提示词（最低优先级）

### 4.2 变量替换
支持以下变量：
- `{domain}` - 当前处理领域
- `{context}` - 上下文信息
- `{user_level}` - 用户级别
- `{confidence_threshold}` - 置信度阈值

### 4.3 模板继承
- 基础模板：`templates/base_agent.yaml`
- Agent继承并扩展基础模板

## 5. 使用示例

### 5.1 加载Agent提示词
```python
from app.prompts.loader import AgentPromptLoader

loader = AgentPromptLoader()
prompt = loader.load_agent_prompt("tax")
```

### 5.2 动态渲染
```python
from app.prompts.loader import AgentPromptLoader

loader = AgentPromptLoader()
prompt = loader.render_agent_prompt(
    agent_name="tax",
    context={
        "domain": "vat",
        "confidence_threshold": 0.8
    }
)
```

## 6. 迁移指南

### 6.1 从旧结构迁移
旧位置 → 新位置：
- `react_agent.txt` → `agents/react/system.md`
- `agents/finance_specialist/` → `agents/finance/`
- `agents/tax_specialist/` → `agents/tax/`
- `agents/legal_specialist/` → `agents/legal/`

### 6.2 Agent合并
- `ReportAgent` + `ReportGenerator` → `report`
- `ReviewedReActAgent` 功能由 `output` 接管
- `ReflectionSpecialist` → `llm_functions.review_quality()` 函数

## 7. 命名规范

### 7.1 Agent名称
- 使用小写字母
- 使用下划线分隔（如 `tax_specialist` → `tax`）
- 与目录名保持一致

### 7.2 文件命名
- 配置文件：`agent.yaml`
- 主提示词：`system.md`
- 少样本：`*.yaml`
- 子模块：`*.md` 或 `*.yaml`

## 8. 版本管理

- 每个Agent有独立版本号
- 支持版本回滚
- 变更记录在 `CHANGELOG.md`
