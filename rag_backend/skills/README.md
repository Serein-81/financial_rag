# Skills（Agent 技能包）

受 Claude Code Skills 规范启发的自研技能系统。**Skills ≠ Tools**：Tools 是原子 API 调用，Skills 是包含引导流程（SKILL.md）、精确脚本（scripts/）和领域知识（references/）的完整业务工作流。

框架代码在 `app/skills/`（registry/loader/matcher/executor/validator），本目录存放**技能包内容**。

## 目录结构（域范围隔离）

```text
skills/
  finance/
    financial-data-entry/        # 财务数据录入校验与提交
  tax/
    corporate-tax-check/         # 企业所得税合规检查
    vat-calculation/             # 增值税计算
  legal/
    legal-compliance-search/     # 法规合规检索与匹配（Tavily）
    tax-law-research/            # 联网搜索最新税务法律知识
  public/
    policy-crawl/                # 爬取政府政策 + 企业匹配 + SSE 通知
    enterprise-profile/          # 企业画像
```

共 **7 个内置技能**。domain 从父目录名推断（合法值 finance/tax/legal/public），public 技能跨域可见；也支持扁平结构（domain 写在 SKILL.md frontmatter）。

## 单个技能包约定

```text
{skill-name}/
  SKILL.md          # YAML frontmatter（name/description/when_to_use）+ 流程正文
  scripts/          # 可执行脚本（LLM 不擅长的精确计算/外部调用），subprocess 执行读 stdout
  references/       # 按需加载的领域知识文档
  assets/           # 静态资源（可选）
```

## 三级渐进加载

| 级别 | 时机 | 内容 | 实现 |
|---|---|---|---|
| Level 1 | 应用启动 | 仅 frontmatter 元数据（约 100 tokens/技能），预计算 description+when_to_use 的 embedding | `SkillRegistry.initialize()`（main.py lifespan 中扫描） |
| Level 2 | 技能激活 | 完整 SKILL.md 正文注入 Agent system prompt（建议 <5K tokens） | `SkillLoader.load_full_body()` |
| Level 3 | 运行时 | references/assets 按需读取；scripts 隔离执行不进上下文 | `SkillLoader.load_reference()` / `load_asset()` |

## 激活链路

```
intent_router 识别 domain
  → LangGraph skill_dispatch 节点匹配技能（embedding 相似度）
  → inject_skill_context() 将 SKILL.md 正文追加到专家 system prompt
  → 专家按流程执行（必要时经 scripts/ 调用精确计算）
```

`format_domain_skill_descriptions(domain)` 把「本域 + public」技能描述渲染进 Agent 提示词的 `{skill_descriptions}` 变量。

## 与 prompts/skills 的区别

`app/prompts/skills/` 下另有 8 个**提示词型技能模板**（skill.yaml + instructions.md，如 enterprise_knowledge_search、web_research、policy_impact_analysis、contract_risk_review 等），属于提示词资产，不走 SKILL.md 三级加载。

## 新增技能

1. 在对应域目录创建 `{skill-name}/SKILL.md`（含 frontmatter：name、description、when_to_use）。
2. 需要精确计算时添加 `scripts/`，需要领域知识时添加 `references/`。
3. 重启服务（lifespan 重新扫描）；`pytest tests/unit/test_skill_loader.py` 验证。
